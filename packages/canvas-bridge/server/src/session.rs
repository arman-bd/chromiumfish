//! Per-connection session state — owns the open canvases / GL contexts
//! and dispatches incoming protocol messages to the right backend.

use std::collections::HashMap;

use canvas_bridge_proto::{
    decode, CanvasId, ClientMsg, ErrorCode, ServerMsg, PROTOCOL_VERSION,
};
use tracing::{debug, warn};

use crate::{canvas2d::Canvas2DContext, fonts, webgl::WebGLContext};

pub struct Session {
    canvases_2d: HashMap<CanvasId, Canvas2DContext>,
    gl_contexts: HashMap<CanvasId, WebGLContext>,
    /// Persona seed reported by the client; for now we just log it,
    /// but a future iteration may key offscreen GL contexts by it so
    /// per-persona WebGL state stays isolated.
    persona_seed: u64,
}

impl Session {
    pub fn new() -> Self {
        Self {
            canvases_2d: HashMap::new(),
            gl_contexts: HashMap::new(),
            persona_seed: 0,
        }
    }

    /// Returns zero or more `ServerMsg` replies for the given client
    /// frame.
    ///
    /// **Push semantics for ops, pull for readbacks.** Write-only
    /// messages (Canvas2DOp, Canvas2DBatch, WebGLOp, CreateCanvas*,
    /// DestroyCanvas) return `vec![]` on success — the client doesn't
    /// wait for an ack, halving frame count for op streams.
    /// Errors are still pushed asynchronously.
    /// Readback messages (Get*, Welcome) always return their reply.
    pub fn handle(&mut self, frame: &[u8]) -> Vec<ServerMsg> {
        let msg: ClientMsg = match decode(frame) {
            Ok(m) => m,
            Err(e) => {
                return vec![ServerMsg::Error {
                    code: ErrorCode::Internal,
                    message: format!("decode: {e}"),
                }]
            }
        };

        match msg {
            ClientMsg::Hello {
                protocol_version,
                client_version,
                persona_seed,
            } => {
                if protocol_version != PROTOCOL_VERSION {
                    return vec![ServerMsg::Error {
                        code: ErrorCode::BadProtocolVersion,
                        message: format!(
                            "server protocol v{PROTOCOL_VERSION}, client v{protocol_version}"
                        ),
                    }];
                }
                self.persona_seed = persona_seed;
                debug!(?client_version, persona_seed, "client hello");
                let info = platform_info();
                vec![ServerMsg::Welcome {
                    protocol_version: PROTOCOL_VERSION,
                    server_version: env!("CARGO_PKG_VERSION").into(),
                    os: info.os.into(),
                    gpu_renderer: info.gpu_renderer.into(),
                    gpu_vendor: info.gpu_vendor.into(),
                }]
            }

            /* ------------ Canvas2D ------------ */
            ClientMsg::CreateCanvas2D { id, width, height, opaque } => {
                match Canvas2DContext::new(width, height, opaque) {
                    Ok(ctx) => {
                        self.canvases_2d.insert(id, ctx);
                        vec![] // push semantics
                    }
                    Err(e) => vec![ServerMsg::Error {
                        code: ErrorCode::Internal,
                        message: e.to_string(),
                    }],
                }
            }
            ClientMsg::Canvas2DOp { id, op } => match self.canvases_2d.get_mut(&id) {
                Some(ctx) => match ctx.replay(op) {
                    Ok(()) => vec![],
                    Err(e) => vec![ServerMsg::Error {
                        code: ErrorCode::UnsupportedOp,
                        message: e.to_string(),
                    }],
                },
                None => vec![unknown(id)],
            },
            ClientMsg::Canvas2DBatch { id, ops } => match self.canvases_2d.get_mut(&id) {
                Some(ctx) => {
                    let mut errors = Vec::new();
                    for op in ops {
                        if let Err(e) = ctx.replay(op) {
                            errors.push(ServerMsg::Error {
                                code: ErrorCode::UnsupportedOp,
                                message: e.to_string(),
                            });
                            // Continue rest of batch — fpjs probes
                            // are tolerant of partial failure and
                            // we'd rather see errors per-op than
                            // halt the whole batch on the first.
                        }
                    }
                    errors
                }
                None => vec![unknown(id)],
            },
            ClientMsg::GetCanvas2DPng { id, mime, quality } => match self.canvases_2d.get_mut(&id)
            {
                Some(ctx) => match ctx.encode(&mime, quality) {
                    Ok(bytes) => vec![ServerMsg::CanvasPng { id, bytes, mime }],
                    Err(e) => vec![ServerMsg::Error {
                        code: ErrorCode::Internal,
                        message: e.to_string(),
                    }],
                },
                None => vec![unknown(id)],
            },
            ClientMsg::GetCanvas2DImageData { id, x, y, w, h } => {
                match self.canvases_2d.get_mut(&id) {
                    Some(ctx) => match ctx.image_data(x, y, w, h) {
                        Ok(pixels) => vec![ServerMsg::ImageData { id, w, h, pixels }],
                        Err(e) => vec![ServerMsg::Error {
                            code: ErrorCode::Internal,
                            message: e.to_string(),
                        }],
                    },
                    None => vec![unknown(id)],
                }
            }

            /* ------------ WebGL ------------ */
            ClientMsg::CreateWebGL { id, width, height, attrs, version } => {
                if width > crate::canvas2d::MAX_CANVAS_DIM
                    || height > crate::canvas2d::MAX_CANVAS_DIM
                {
                    vec![ServerMsg::Error {
                        code: ErrorCode::UnsupportedOp,
                        message: format!(
                            "webgl {width}x{height} exceeds max dimension {}",
                            crate::canvas2d::MAX_CANVAS_DIM
                        ),
                    }]
                } else {
                    self.gl_contexts
                        .insert(id, WebGLContext::new(width, height, attrs, version));
                    vec![]
                }
            }
            ClientMsg::WebGLOp { id, op } => match self.gl_contexts.get_mut(&id) {
                Some(ctx) => match ctx.replay(op) {
                    Ok(()) => vec![],
                    Err(e) => vec![ServerMsg::Error {
                        code: ErrorCode::UnsupportedOp,
                        message: e.to_string(),
                    }],
                },
                None => vec![unknown(id)],
            },
            ClientMsg::WebGLReadPixels { id, x, y, w, h, format, ty } => {
                match self.gl_contexts.get_mut(&id) {
                    Some(ctx) => match ctx.read_pixels(x, y, w, h, format, ty) {
                        Ok(pixels) => vec![ServerMsg::ImageData { id, w, h, pixels }],
                        Err(e) => vec![ServerMsg::Error {
                            code: ErrorCode::UnsupportedOp,
                            message: e.to_string(),
                        }],
                    },
                    None => vec![unknown(id)],
                }
            }
            ClientMsg::WebGLQueryStrings { id, keys } => match self.gl_contexts.get_mut(&id) {
                Some(ctx) => vec![ServerMsg::WebGLStrings {
                    id,
                    values: ctx.query_strings(&keys),
                }],
                None => vec![unknown(id)],
            },

            /* ------------ Fonts ------------ */
            ClientMsg::MeasureText { text, families, sizes_px } => {
                match fonts::measure(&text, &families, &sizes_px) {
                    Ok(metrics) => vec![ServerMsg::TextMetrics { metrics }],
                    Err(e) => {
                        warn!(err = %e, "font measure failed");
                        vec![ServerMsg::Error {
                            code: ErrorCode::Internal,
                            message: e.to_string(),
                        }]
                    }
                }
            }

            ClientMsg::DestroyCanvas { id } => {
                self.canvases_2d.remove(&id);
                self.gl_contexts.remove(&id);
                vec![]
            }
        }
    }
}

fn unknown(id: CanvasId) -> ServerMsg {
    ServerMsg::Error {
        code: ErrorCode::UnknownCanvas,
        message: format!("no canvas with id={}", id.0),
    }
}

struct PlatformInfo {
    os: &'static str,
    gpu_renderer: &'static str,
    gpu_vendor: &'static str,
}

fn platform_info() -> PlatformInfo {
    // GPU strings are still placeholders until the WebGL backend
    // actually creates an off-screen GL context. They reflect the
    // *intended* identity for the platform.
    #[cfg(target_os = "windows")]
    {
        PlatformInfo {
            os: "windows",
            gpu_renderer:
                "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
            gpu_vendor: "Google Inc. (AMD)",
        }
    }
    #[cfg(target_os = "macos")]
    {
        PlatformInfo {
            os: "macos",
            gpu_renderer: "ANGLE (Apple, Apple M1, OpenGL 4.1)",
            gpu_vendor: "Google Inc. (Apple)",
        }
    }
    #[cfg(target_os = "linux")]
    {
        PlatformInfo {
            os: "linux",
            gpu_renderer:
                "ANGLE (Intel, Mesa Intel(R) UHD Graphics, OpenGL 4.6)",
            gpu_vendor: "Google Inc. (Intel)",
        }
    }
}
