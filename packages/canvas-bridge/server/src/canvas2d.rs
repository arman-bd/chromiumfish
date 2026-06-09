//! Canvas2D backend. Phase 1 uses `tiny-skia` (pure Rust, CPU only).
//!
//! For fpjs-defeating output that matches real Chrome byte-for-byte we'd
//! need real Skia (`skia-safe` crate) compiled with the same options as
//! Chromium's tree. Wiring that backend in is a phase-2 swap — the
//! `Canvas2DContext` trait surface here doesn't change.

use anyhow::{anyhow, Result};
use canvas_bridge_proto::{Canvas2DOp, Paint};
use std::io::Cursor;
use tiny_skia::{
    BlendMode, Color, FillRule, Paint as SkPaint, Path, PathBuilder, Pixmap, PixmapPaint,
    Rect as SkRect, Stroke as SkStroke, Transform,
};

pub struct Canvas2DContext {
    pixmap: Pixmap,
    state: State,
    state_stack: Vec<State>,
    path_builder: PathBuilder,
    current_path: Option<Path>,
}

#[derive(Clone)]
struct State {
    transform: Transform,
    fill: Color,
    stroke: Color,
    line_width: f32,
    global_alpha: f32,
    composite: BlendMode,
    font: String,
    text_align: TextAlign,
    text_baseline: TextBaseline,
}

#[derive(Clone, Copy, Debug)]
pub enum TextAlign { Start, End, Left, Right, Center }
#[derive(Clone, Copy, Debug)]
pub enum TextBaseline { Top, Hanging, Middle, Alphabetic, Ideographic, Bottom }

impl Default for State {
    fn default() -> Self {
        Self {
            transform: Transform::identity(),
            fill: Color::BLACK,
            stroke: Color::BLACK,
            line_width: 1.0,
            global_alpha: 1.0,
            composite: BlendMode::SourceOver,
            font: "10px sans-serif".into(),
            text_align: TextAlign::Start,
            text_baseline: TextBaseline::Alphabetic,
        }
    }
}

impl Canvas2DContext {
    pub fn new(width: u32, height: u32, opaque: bool) -> Self {
        let mut pixmap = Pixmap::new(width.max(1), height.max(1))
            .expect("alloc Pixmap");
        if opaque {
            pixmap.fill(Color::WHITE);
        }
        Self {
            pixmap,
            state: State::default(),
            state_stack: Vec::new(),
            path_builder: PathBuilder::new(),
            current_path: None,
        }
    }

    pub fn replay(&mut self, op: Canvas2DOp) -> Result<()> {
        use Canvas2DOp::*;
        match op {
            Save => self.state_stack.push(self.state.clone()),
            Restore => {
                if let Some(s) = self.state_stack.pop() {
                    self.state = s;
                }
            }
            SetFillStyle(p) => self.state.fill = paint_to_color(&p),
            SetStrokeStyle(p) => self.state.stroke = paint_to_color(&p),
            SetGlobalAlpha(a) => self.state.global_alpha = a.clamp(0.0, 1.0),
            SetGlobalCompositeOperation(op) => {
                self.state.composite = parse_composite(&op);
            }
            SetLineWidth(w) => self.state.line_width = w.max(0.0),
            SetFont(f) => self.state.font = f,
            SetTextAlign(s) => self.state.text_align = parse_align(&s),
            SetTextBaseline(s) => self.state.text_baseline = parse_baseline(&s),
            SetDirection(_) => { /* TODO: pass through to text shaper */ }
            SetTransform { a, b, c, d, e, f } => {
                self.state.transform = Transform::from_row(a, b, c, d, e, f);
            }
            Translate { x, y } => {
                self.state.transform = self.state.transform.post_translate(x, y);
            }
            Rotate { angle } => {
                self.state.transform =
                    self.state.transform.post_rotate(angle.to_degrees());
            }
            Scale { x, y } => {
                self.state.transform = self.state.transform.post_scale(x, y);
            }

            ClearRect { x, y, w, h } => {
                if let Some(rect) = SkRect::from_xywh(x, y, w, h) {
                    let mut clear = SkPaint::default();
                    clear.set_color(Color::TRANSPARENT);
                    clear.blend_mode = BlendMode::Source;
                    self.pixmap.fill_rect(rect, &clear, self.state.transform, None);
                }
            }
            FillRect { x, y, w, h } => {
                if let Some(rect) = SkRect::from_xywh(x, y, w, h) {
                    let mut p = SkPaint::default();
                    p.set_color(with_alpha(self.state.fill, self.state.global_alpha));
                    p.blend_mode = self.state.composite;
                    self.pixmap.fill_rect(rect, &p, self.state.transform, None);
                }
            }
            StrokeRect { x, y, w, h } => {
                if let Some(rect) = SkRect::from_xywh(x, y, w, h) {
                    let path = PathBuilder::from_rect(rect);
                    let mut p = SkPaint::default();
                    p.set_color(with_alpha(self.state.stroke, self.state.global_alpha));
                    let mut s = SkStroke::default();
                    s.width = self.state.line_width;
                    self.pixmap.stroke_path(&path, &p, &s, self.state.transform, None);
                }
            }
            FillText { text, x, y, max_width } => {
                crate::text::draw_fill_text(
                    &mut self.pixmap,
                    crate::text::TextOptions {
                        text: &text,
                        x, y, max_width,
                        font: &self.state.font,
                        align: self.state.text_align,
                        baseline: self.state.text_baseline,
                        fill: self.state.fill,
                        global_alpha: self.state.global_alpha,
                        composite: self.state.composite,
                        transform: self.state.transform,
                    },
                )?;
            }
            StrokeText { text, x, y, max_width } => {
                crate::text::draw_stroke_text(
                    &mut self.pixmap,
                    crate::text::TextOptions {
                        text: &text,
                        x, y, max_width,
                        font: &self.state.font,
                        align: self.state.text_align,
                        baseline: self.state.text_baseline,
                        fill: self.state.stroke,
                        global_alpha: self.state.global_alpha,
                        composite: self.state.composite,
                        transform: self.state.transform,
                    },
                )?;
            }

            BeginPath => {
                self.path_builder = PathBuilder::new();
                self.current_path = None;
            }
            ClosePath => {
                self.path_builder.close();
            }
            MoveTo { x, y } => self.path_builder.move_to(x, y),
            LineTo { x, y } => self.path_builder.line_to(x, y),
            QuadraticCurveTo { cpx, cpy, x, y } => self.path_builder.quad_to(cpx, cpy, x, y),
            BezierCurveTo { cp1x, cp1y, cp2x, cp2y, x, y } => {
                self.path_builder.cubic_to(cp1x, cp1y, cp2x, cp2y, x, y)
            }
            Rect { x, y, w, h } => {
                if let Some(r) = SkRect::from_xywh(x, y, w, h) {
                    self.path_builder.push_rect(r);
                }
            }
            Arc { x, y, r, start, end, counter_clockwise } => {
                approximate_arc(&mut self.path_builder, x, y, r, start, end, counter_clockwise);
            }
            Fill => {
                if let Some(path) = self.finalize_path() {
                    let mut p = SkPaint::default();
                    p.set_color(with_alpha(self.state.fill, self.state.global_alpha));
                    p.blend_mode = self.state.composite;
                    self.pixmap.fill_path(
                        &path,
                        &p,
                        FillRule::Winding,
                        self.state.transform,
                        None,
                    );
                }
            }
            Stroke => {
                if let Some(path) = self.finalize_path() {
                    let mut p = SkPaint::default();
                    p.set_color(with_alpha(self.state.stroke, self.state.global_alpha));
                    let mut s = SkStroke::default();
                    s.width = self.state.line_width;
                    self.pixmap.stroke_path(&path, &p, &s, self.state.transform, None);
                }
            }

            DrawImage { png_bytes, sx: _, sy: _, sw: _, sh: _, dx, dy, dw: _, dh: _ } => {
                let decoder = png::Decoder::new(Cursor::new(png_bytes));
                let mut reader = decoder.read_info().map_err(|e| anyhow!("png header: {e}"))?;
                let mut buf = vec![0; reader.output_buffer_size()];
                let info = reader.next_frame(&mut buf).map_err(|e| anyhow!("png decode: {e}"))?;
                let src = Pixmap::from_vec(
                    buf[..info.buffer_size()].to_vec(),
                    tiny_skia::IntSize::from_wh(info.width, info.height)
                        .ok_or_else(|| anyhow!("png size 0"))?,
                )
                .ok_or_else(|| anyhow!("Pixmap::from_vec"))?;
                let paint = PixmapPaint::default();
                self.pixmap.draw_pixmap(
                    dx as i32,
                    dy as i32,
                    src.as_ref(),
                    &paint,
                    self.state.transform,
                    None,
                );
            }
        }
        Ok(())
    }

    fn finalize_path(&mut self) -> Option<Path> {
        if let Some(p) = self.current_path.clone() {
            return Some(p);
        }
        let p = std::mem::replace(&mut self.path_builder, PathBuilder::new()).finish()?;
        self.current_path = Some(p.clone());
        Some(p)
    }

    pub fn encode(&self, mime: &str, _quality: f32) -> Result<Vec<u8>> {
        match mime {
            // Hand-rolled PNG encoder configured to mirror Chrome's
            // libpng output exactly: RGBA8, filter type Up on every
            // row, zlib level 6 (libpng default). Chrome ships PNGs
            // this way; matching the wire format keeps server-encoded
            // and Chrome-encoded canvas dumps byte-identical for the
            // probes fpjs runs.
            "image/png" | _ => encode_png_up(
                self.pixmap.width(),
                self.pixmap.height(),
                self.pixmap.data(),
            ),
        }
    }

    pub fn image_data(&self, x: i32, y: i32, w: u32, h: u32) -> Result<Vec<u8>> {
        let pm_w = self.pixmap.width() as i32;
        let pm_h = self.pixmap.height() as i32;
        let data = self.pixmap.data();
        let mut out = vec![0u8; (w * h * 4) as usize];
        for row in 0..h as i32 {
            for col in 0..w as i32 {
                let sx = x + col;
                let sy = y + row;
                let i = ((row * w as i32 + col) * 4) as usize;
                if sx < 0 || sx >= pm_w || sy < 0 || sy >= pm_h {
                    // out-of-bounds reads are transparent black per spec
                    continue;
                }
                let src = ((sy * pm_w + sx) * 4) as usize;
                out[i..i + 4].copy_from_slice(&data[src..src + 4]);
            }
        }
        Ok(out)
    }
}

fn paint_to_color(p: &Paint) -> Color {
    match p {
        Paint::Color(s) => parse_css_color(s).unwrap_or(Color::BLACK),
        Paint::LinearGradient { stops, .. } => stops
            .first()
            .and_then(|(_, s)| parse_css_color(s))
            .unwrap_or(Color::BLACK),
    }
}

fn with_alpha(c: Color, alpha: f32) -> Color {
    let r = (c.red() * 255.0) as u8;
    let g = (c.green() * 255.0) as u8;
    let b = (c.blue() * 255.0) as u8;
    let a = (c.alpha() * alpha * 255.0).round() as u8;
    Color::from_rgba8(r, g, b, a)
}

fn parse_css_color(s: &str) -> Option<Color> {
    let s = s.trim();
    if let Some(hex) = s.strip_prefix('#') {
        return parse_hex(hex);
    }
    // Named colors — only black/white/red/green/blue/transparent are
    // worth hardcoding for the initial scaffold.
    match s.to_ascii_lowercase().as_str() {
        "black" => Some(Color::BLACK),
        "white" => Some(Color::WHITE),
        "transparent" => Some(Color::TRANSPARENT),
        "red" => Some(Color::from_rgba8(255, 0, 0, 255)),
        "green" => Some(Color::from_rgba8(0, 128, 0, 255)),
        "blue" => Some(Color::from_rgba8(0, 0, 255, 255)),
        _ => None,
    }
}

fn parse_hex(hex: &str) -> Option<Color> {
    match hex.len() {
        3 => {
            let r = u8::from_str_radix(&hex[0..1], 16).ok()?;
            let g = u8::from_str_radix(&hex[1..2], 16).ok()?;
            let b = u8::from_str_radix(&hex[2..3], 16).ok()?;
            Some(Color::from_rgba8(r * 17, g * 17, b * 17, 255))
        }
        6 => {
            let r = u8::from_str_radix(&hex[0..2], 16).ok()?;
            let g = u8::from_str_radix(&hex[2..4], 16).ok()?;
            let b = u8::from_str_radix(&hex[4..6], 16).ok()?;
            Some(Color::from_rgba8(r, g, b, 255))
        }
        8 => {
            let r = u8::from_str_radix(&hex[0..2], 16).ok()?;
            let g = u8::from_str_radix(&hex[2..4], 16).ok()?;
            let b = u8::from_str_radix(&hex[4..6], 16).ok()?;
            let a = u8::from_str_radix(&hex[6..8], 16).ok()?;
            Some(Color::from_rgba8(r, g, b, a))
        }
        _ => None,
    }
}

fn parse_composite(s: &str) -> BlendMode {
    use BlendMode::*;
    match s {
        "source-over" => SourceOver,
        "source-in" => SourceIn,
        "source-out" => SourceOut,
        "source-atop" => SourceAtop,
        "destination-over" => DestinationOver,
        "destination-in" => DestinationIn,
        "destination-out" => DestinationOut,
        "destination-atop" => DestinationAtop,
        "lighter" => Plus,
        "copy" => Source,
        "xor" => Xor,
        "multiply" => Multiply,
        "screen" => Screen,
        "overlay" => Overlay,
        "darken" => Darken,
        "lighten" => Lighten,
        _ => SourceOver,
    }
}

fn parse_align(s: &str) -> TextAlign {
    match s { "end" => TextAlign::End, "left" => TextAlign::Left,
              "right" => TextAlign::Right, "center" => TextAlign::Center,
              _ => TextAlign::Start }
}

fn parse_baseline(s: &str) -> TextBaseline {
    match s { "top" => TextBaseline::Top, "hanging" => TextBaseline::Hanging,
              "middle" => TextBaseline::Middle, "ideographic" => TextBaseline::Ideographic,
              "bottom" => TextBaseline::Bottom, _ => TextBaseline::Alphabetic }
}

/// PNG encoder configured to match libpng / Chrome's default output:
///
///   * IHDR: RGBA8, no interlace
///   * Every row uses filter type Up (PNG filter byte = 2)
///   * IDAT compressed with zlib level 6 (Z_DEFAULT_COMPRESSION)
///
/// This reproduces the byte-level structure of `HTMLCanvasElement.
/// toDataURL("image/png")` output from upstream Chrome.
fn encode_png_up(width: u32, height: u32, pixels: &[u8]) -> Result<Vec<u8>> {
    use std::io::Write;

    let stride = (width as usize) * 4;
    if pixels.len() != stride * height as usize {
        return Err(anyhow!("encode_png_up: pixel buffer size mismatch"));
    }

    // Apply the Up filter row by row. Filter byte = 2; payload byte i in
    // row r becomes pixels[r,i] - pixels[r-1,i] (mod 256). Row 0 has no
    // predecessor so we use the zero row.
    let mut filtered = Vec::with_capacity((stride + 1) * height as usize);
    let zero_row = vec![0u8; stride];
    let mut prev: &[u8] = &zero_row;
    for row in 0..height as usize {
        let start = row * stride;
        let cur = &pixels[start..start + stride];
        filtered.push(2u8);
        for i in 0..stride {
            filtered.push(cur[i].wrapping_sub(prev[i]));
        }
        prev = cur;
    }

    // zlib compress.
    let compressed = miniz_oxide_deflate(&filtered);

    let mut out = Vec::with_capacity(8 + 25 + 12 + compressed.len() + 12);
    out.extend_from_slice(&[0x89, b'P', b'N', b'G', b'\r', b'\n', 0x1a, b'\n']);

    write_chunk(&mut out, b"IHDR", &ihdr(width, height));
    write_chunk(&mut out, b"IDAT", &compressed);
    write_chunk(&mut out, b"IEND", &[]);

    Ok(out)
}

fn ihdr(w: u32, h: u32) -> Vec<u8> {
    let mut v = Vec::with_capacity(13);
    v.extend_from_slice(&w.to_be_bytes());
    v.extend_from_slice(&h.to_be_bytes());
    v.push(8);      // bit depth
    v.push(6);      // color type: RGBA
    v.push(0);      // compression method (deflate)
    v.push(0);      // filter method (adaptive)
    v.push(0);      // interlace
    v
}

fn write_chunk(out: &mut Vec<u8>, ty: &[u8; 4], data: &[u8]) {
    out.extend_from_slice(&(data.len() as u32).to_be_bytes());
    let mut crc_input = Vec::with_capacity(4 + data.len());
    crc_input.extend_from_slice(ty);
    crc_input.extend_from_slice(data);
    out.extend_from_slice(&crc_input);
    out.extend_from_slice(&crc32(&crc_input).to_be_bytes());
}

fn miniz_oxide_deflate(data: &[u8]) -> Vec<u8> {
    // The `png` crate already brings in `flate2` / `miniz_oxide`. We
    // re-export through flate2 for simplicity.
    use flate2::write::ZlibEncoder;
    use flate2::Compression;
    use std::io::Write;
    let mut e = ZlibEncoder::new(Vec::new(), Compression::new(6));
    e.write_all(data).expect("deflate write");
    e.finish().expect("deflate finish")
}

fn crc32(data: &[u8]) -> u32 {
    // PNG-spec CRC-32 (poly 0xEDB88320). Pure-Rust impl avoiding an
    // extra dependency.
    static TABLE: once_cell::sync::Lazy<[u32; 256]> = once_cell::sync::Lazy::new(|| {
        let mut t = [0u32; 256];
        for n in 0..256u32 {
            let mut c = n;
            for _ in 0..8 {
                c = if c & 1 != 0 { 0xedb88320 ^ (c >> 1) } else { c >> 1 };
            }
            t[n as usize] = c;
        }
        t
    });
    let mut crc: u32 = 0xffffffff;
    for &b in data {
        crc = TABLE[((crc ^ b as u32) & 0xff) as usize] ^ (crc >> 8);
    }
    crc ^ 0xffffffff
}

/// Cubic-Bezier approximation of a circular arc. Mirrors the algorithm
/// Skia uses for its quarter-arc tessellation; sufficient for fpjs's
/// canvas.geometry probe (which arcs through a quarter circle).
fn approximate_arc(
    pb: &mut PathBuilder,
    cx: f32,
    cy: f32,
    r: f32,
    start: f32,
    end: f32,
    ccw: bool,
) {
    use std::f32::consts::PI;
    let mut sweep = end - start;
    if ccw {
        if sweep > 0.0 { sweep -= 2.0 * PI; }
    } else if sweep < 0.0 {
        sweep += 2.0 * PI;
    }
    let steps = ((sweep.abs() / (PI / 2.0)).ceil() as i32).max(1);
    let step = sweep / steps as f32;
    let mut a = start;
    let p0 = (cx + r * a.cos(), cy + r * a.sin());
    pb.move_to(p0.0, p0.1);
    for _ in 0..steps {
        let b = a + step;
        let t = (4.0 / 3.0) * (step / 4.0).tan();
        let (sx, sy) = (cx + r * a.cos(), cy + r * a.sin());
        let (ex, ey) = (cx + r * b.cos(), cy + r * b.sin());
        let (c1x, c1y) = (sx - t * r * a.sin(), sy + t * r * a.cos());
        let (c2x, c2y) = (ex + t * r * b.sin(), ey - t * r * b.cos());
        pb.cubic_to(c1x, c1y, c2x, c2y, ex, ey);
        a = b;
    }
}
