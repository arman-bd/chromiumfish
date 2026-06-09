//! Wire protocol for canvas-bridge.
//!
//! All messages are msgpack-encoded on the WebSocket binary channel. Each
//! frame is a single `ClientMsg` or `ServerMsg`. The protocol is stateful
//! per-connection: the client opens canvases (2D or WebGL), streams ops
//! into them, then asks for a pixel readback when the page calls
//! `toDataURL` / `getImageData` / `readPixels`.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};

pub const PROTOCOL_VERSION: u32 = 1;

/// Canvas handle. Allocated by the client; the server treats it as opaque.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct CanvasId(pub u32);

/// All messages from browser → server.
#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "t", content = "v")]
pub enum ClientMsg {
    /// First message on the channel. Echoed by `ServerMsg::Welcome`.
    Hello {
        protocol_version: u32,
        client_version: String,
        /// Persona seed currently in use by the browser; the server may
        /// use this to keep per-persona offscreen contexts isolated.
        persona_seed: u64,
    },

    /* ---------- Canvas2D ---------- */
    CreateCanvas2D {
        id: CanvasId,
        width: u32,
        height: u32,
        /// Set to true if the page asked for a non-alpha context.
        opaque: bool,
    },
    Canvas2DOp {
        id: CanvasId,
        op: Canvas2DOp,
    },
    /// Bulk op streaming. Browser collects ops into a per-canvas buffer
    /// and flushes the buffer in one frame instead of one-frame-per-op.
    /// Server replays them in order. Saves ~99% of WebSocket framing
    /// overhead for fpjs-class probes which issue ~100 ops per canvas.
    Canvas2DBatch {
        id: CanvasId,
        ops: Vec<Canvas2DOp>,
    },
    /// Equivalent of `HTMLCanvasElement.toDataURL` — server returns
    /// `ServerMsg::CanvasPng`. The client is responsible for base64-
    /// encoding the bytes if the page asked for a data URL.
    GetCanvas2DPng {
        id: CanvasId,
        /// "image/png" or "image/jpeg" or "image/webp". Server may
        /// fall back to PNG on unknown mime types.
        mime: String,
        /// 0.0..=1.0 for lossy formats; ignored for PNG.
        quality: f32,
    },
    /// Equivalent of `getImageData` — server returns
    /// `ServerMsg::ImageData` with raw RGBA8 (premultiplied per spec).
    GetCanvas2DImageData {
        id: CanvasId,
        x: i32,
        y: i32,
        w: u32,
        h: u32,
    },

    /* ---------- WebGL ---------- */
    CreateWebGL {
        id: CanvasId,
        width: u32,
        height: u32,
        attrs: WebGLAttrs,
        /// 1 for WebGL1, 2 for WebGL2.
        version: u8,
    },
    WebGLOp {
        id: CanvasId,
        op: WebGLOp,
    },
    WebGLReadPixels {
        id: CanvasId,
        x: i32,
        y: i32,
        w: u32,
        h: u32,
        format: u32,
        ty: u32,
    },
    /// Mirror of WebGLRenderingContext.getParameter / getSupportedExtensions
    /// so the browser-side WebGL extension hashes (fpjs's webgl_extensions
    /// block) come from the server's GL stack.
    WebGLQueryStrings {
        id: CanvasId,
        /// e.g. "GL_VERSION", "GL_RENDERER", "GL_EXTENSIONS".
        keys: Vec<String>,
    },

    /* ---------- Fonts ---------- */
    /// Mirror of the fpjs font-presence + font-metric probes. Returns
    /// the rendered text box size for each (family, size) pair using
    /// the server host's native text shaper (DirectWrite on Windows,
    /// CoreText on macOS, FontConfig+HarfBuzz on Linux).
    MeasureText {
        text: String,
        families: Vec<String>,
        sizes_px: Vec<f32>,
    },
    /// Drop the server-side handle. Client should send this when the
    /// HTMLCanvasElement is GC'd.
    DestroyCanvas {
        id: CanvasId,
    },
}

/// All messages from server → browser.
#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "t", content = "v")]
pub enum ServerMsg {
    Welcome {
        protocol_version: u32,
        server_version: String,
        /// "windows" / "macos" / "linux"
        os: String,
        /// GPU renderer string from the server's GL context. Lets the
        /// browser report a consistent unmasked-renderer to JS.
        gpu_renderer: String,
        gpu_vendor: String,
    },
    /// Successful canvas readback (PNG/JPEG/WebP bytes per the request mime).
    CanvasPng {
        id: CanvasId,
        #[serde(with = "serde_bytes")]
        bytes: Vec<u8>,
        mime: String,
    },
    /// Raw RGBA8 pixels from getImageData / readPixels.
    ImageData {
        id: CanvasId,
        w: u32,
        h: u32,
        #[serde(with = "serde_bytes")]
        pixels: Vec<u8>,
    },
    /// Reply to WebGLQueryStrings.
    WebGLStrings {
        id: CanvasId,
        values: Vec<String>,
    },
    /// Reply to MeasureText. `metrics[i][j]` is the metric for
    /// families[i] at sizes_px[j]. Encoded as { width, ascent,
    /// descent, ideographicBaseline } to mirror TextMetrics on the
    /// browser side.
    TextMetrics {
        metrics: Vec<Vec<TextMetric>>,
    },
    /// Server picked up our op but had nothing to return (used as a
    /// flow-control heartbeat).
    Ack,
    Error {
        code: ErrorCode,
        message: String,
    },
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    BadProtocolVersion,
    AuthFailed,
    UnknownCanvas,
    UnsupportedOp,
    Internal,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy)]
pub struct TextMetric {
    pub width: f32,
    pub actual_bounding_box_ascent: f32,
    pub actual_bounding_box_descent: f32,
    pub font_bounding_box_ascent: f32,
    pub font_bounding_box_descent: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, Default)]
pub struct WebGLAttrs {
    pub alpha: bool,
    pub depth: bool,
    pub stencil: bool,
    pub antialias: bool,
    pub premultiplied_alpha: bool,
    pub preserve_drawing_buffer: bool,
    pub fail_if_major_performance_caveat: bool,
}

/// Subset of canvas-2d API. We only need the ops fpjs actually probes
/// (fillText, fillRect, strokeRect, font/text styling, drawImage,
/// arc/path basics) for canvas.text + canvas.geometry hashes. Real
/// production use would grow this enum.
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(tag = "op", content = "args")]
pub enum Canvas2DOp {
    /* ---- state ---- */
    Save,
    Restore,
    SetFillStyle(Paint),
    SetStrokeStyle(Paint),
    SetGlobalAlpha(f32),
    SetGlobalCompositeOperation(String),
    SetLineWidth(f32),
    SetFont(String),
    SetTextAlign(String),
    SetTextBaseline(String),
    SetDirection(String),
    SetTransform { a: f32, b: f32, c: f32, d: f32, e: f32, f: f32 },
    Translate { x: f32, y: f32 },
    Rotate { angle: f32 },
    Scale { x: f32, y: f32 },

    /* ---- drawing ---- */
    ClearRect { x: f32, y: f32, w: f32, h: f32 },
    FillRect { x: f32, y: f32, w: f32, h: f32 },
    StrokeRect { x: f32, y: f32, w: f32, h: f32 },
    FillText { text: String, x: f32, y: f32, max_width: Option<f32> },
    StrokeText { text: String, x: f32, y: f32, max_width: Option<f32> },

    /* ---- paths ---- */
    BeginPath,
    ClosePath,
    MoveTo { x: f32, y: f32 },
    LineTo { x: f32, y: f32 },
    QuadraticCurveTo { cpx: f32, cpy: f32, x: f32, y: f32 },
    BezierCurveTo { cp1x: f32, cp1y: f32, cp2x: f32, cp2y: f32, x: f32, y: f32 },
    Rect { x: f32, y: f32, w: f32, h: f32 },
    Arc { x: f32, y: f32, r: f32, start: f32, end: f32, counter_clockwise: bool },
    Fill,
    Stroke,

    /* ---- images ---- */
    /// Inline bitmap upload + draw. The browser side encodes its image
    /// source as PNG and ships it.
    DrawImage {
        #[serde(with = "serde_bytes")]
        png_bytes: Vec<u8>,
        sx: f32, sy: f32, sw: f32, sh: f32,
        dx: f32, dy: f32, dw: f32, dh: f32,
    },
}

/// Paint subset — fpjs only ever uses CSS color strings, so we keep
/// gradients as a future addition.
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(tag = "k", content = "v")]
pub enum Paint {
    Color(String),
    LinearGradient {
        x0: f32, y0: f32, x1: f32, y1: f32,
        stops: Vec<(f32, String)>,
    },
    // Pattern, RadialGradient, ConicGradient — TODO when needed.
}

/// WebGL op enum, minimal subset that covers fpjs's WebGL fingerprint
/// probe (clear + draw fullscreen quad + readPixels + getParameter).
/// Production would grow this to the full WebGL2 surface; for now we
/// also expose `Raw` for un-modeled ops while iterating.
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(tag = "op", content = "args")]
pub enum WebGLOp {
    ClearColor { r: f32, g: f32, b: f32, a: f32 },
    Clear { mask: u32 },
    Enable(u32),
    Disable(u32),
    Viewport { x: i32, y: i32, w: i32, h: i32 },
    CreateProgram { handle: u32 },
    CreateShader { handle: u32, ty: u32 },
    ShaderSource { shader: u32, source: String },
    CompileShader { shader: u32 },
    AttachShader { program: u32, shader: u32 },
    LinkProgram { program: u32 },
    UseProgram { program: u32 },
    CreateBuffer { handle: u32 },
    BindBuffer { target: u32, buffer: u32 },
    BufferData {
        target: u32,
        #[serde(with = "serde_bytes")]
        data: Vec<u8>,
        usage: u32,
    },
    GetAttribLocation { program: u32, name: String, slot: u32 },
    EnableVertexAttribArray(u32),
    VertexAttribPointer {
        index: u32, size: i32, ty: u32,
        normalized: bool, stride: i32, offset: i32,
    },
    DrawArrays { mode: u32, first: i32, count: i32 },
    DrawElements { mode: u32, count: i32, ty: u32, offset: i32 },

    /// Catch-all for ops we haven't modeled yet. `name` is the GL
    /// function name; args is the raw msgpack-encoded payload the
    /// server-side dispatcher decodes per-op. Lets us iterate without
    /// bumping the protocol version every op.
    Raw {
        name: String,
        #[serde(with = "serde_bytes")]
        args: Vec<u8>,
    },
}

/* ---------- codec ---------- */

/// Convenience: encode a message to a binary WebSocket frame.
pub fn encode<T: Serialize>(msg: &T) -> Result<Vec<u8>, rmp_serde::encode::Error> {
    rmp_serde::to_vec_named(msg)
}

/// Convenience: decode a message from a binary frame.
pub fn decode<'de, T: Deserialize<'de>>(buf: &'de [u8]) -> Result<T, rmp_serde::decode::Error> {
    rmp_serde::from_slice(buf)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_canvas2d_op() {
        let msg = ClientMsg::Canvas2DOp {
            id: CanvasId(7),
            op: Canvas2DOp::FillText {
                text: "Cwm fjordbank glyphs vext quiz".into(),
                x: 4.0,
                y: 17.0,
                max_width: None,
            },
        };
        let bytes = encode(&msg).unwrap();
        let back: ClientMsg = decode(&bytes).unwrap();
        match back {
            ClientMsg::Canvas2DOp { id: CanvasId(7), op: Canvas2DOp::FillText { ref text, .. } } => {
                assert!(text.starts_with("Cwm fjordbank"));
            }
            other => panic!("unexpected roundtrip: {other:?}"),
        }
    }

    #[test]
    fn roundtrip_welcome() {
        let msg = ServerMsg::Welcome {
            protocol_version: PROTOCOL_VERSION,
            server_version: "0.1.0".into(),
            os: "windows".into(),
            gpu_renderer: "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)".into(),
            gpu_vendor: "Google Inc. (AMD)".into(),
        };
        let bytes = encode(&msg).unwrap();
        let back: ServerMsg = decode(&bytes).unwrap();
        assert!(matches!(back, ServerMsg::Welcome { .. }));
    }
}
