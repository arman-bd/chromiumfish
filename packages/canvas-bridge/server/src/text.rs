//! Text rendering for canvas2d `fillText` / `strokeText`.
//!
//! Pipeline: parse the canvas CSS-shorthand font string → resolve a
//! font from the host's `fontdb` → shape the string with `cosmic-text`
//! → rasterize each glyph with `swash` → composite onto the target
//! `tiny_skia::Pixmap` honoring the current paint and transform.
//!
//! Phase-2 swap target: real Skia (`skia-safe`) so the glyph rasterization
//! and subpixel positioning match Chrome bit-for-bit. The shape+layout
//! pipeline here is already close enough for fpjs's
//! `canvas.text` hash to validate equivalence (within antialiasing
//! rounding); the exact pixel match requires Skia.

use anyhow::{anyhow, Result};
use cosmic_text::{
    Attrs, Buffer, Family, FontSystem, Metrics, Shaping, Weight,
};
use once_cell::sync::Lazy;
use std::sync::Mutex;
use swash::scale::{Render, ScaleContext, Source, StrikeWith};
use swash::zeno::{Format, Vector};
use swash::FontRef;
use tiny_skia::{BlendMode, Color, Pixmap, PremultipliedColorU8, Transform};

static FONT_SYSTEM: Lazy<Mutex<FontSystem>> =
    Lazy::new(|| Mutex::new(FontSystem::new()));

#[derive(Clone, Copy, Debug)]
pub struct TextOptions<'a> {
    pub text: &'a str,
    pub x: f32,
    pub y: f32,
    pub max_width: Option<f32>,
    pub font: &'a str,
    pub align: crate::canvas2d::TextAlign,
    pub baseline: crate::canvas2d::TextBaseline,
    pub fill: Color,
    pub global_alpha: f32,
    pub composite: BlendMode,
    pub transform: Transform,
}

pub fn draw_fill_text(pix: &mut Pixmap, opts: TextOptions<'_>) -> Result<()> {
    let parsed = parse_font_string(opts.font);
    let metrics = Metrics::new(parsed.size_px, parsed.size_px * 1.2);

    let mut fs = FONT_SYSTEM
        .lock()
        .map_err(|_| anyhow!("FONT_SYSTEM poisoned"))?;
    let mut buffer = Buffer::new(&mut fs, metrics);
    let mut attrs = Attrs::new();
    let family_owned;
    if let Some(name) = &parsed.family {
        family_owned = name.clone();
        attrs = attrs.family(Family::Name(&family_owned));
    } else {
        attrs = attrs.family(Family::SansSerif);
    }
    if parsed.bold {
        attrs = attrs.weight(Weight::BOLD);
    }
    if parsed.italic {
        attrs = attrs.style(cosmic_text::Style::Italic);
    }

    buffer.set_text(&mut fs, opts.text, attrs, Shaping::Advanced);
    if let Some(w) = opts.max_width {
        buffer.set_size(&mut fs, w, f32::INFINITY);
    } else {
        buffer.set_size(&mut fs, f32::INFINITY, f32::INFINITY);
    }
    buffer.shape_until_scroll(&mut fs);

    // Total width across all runs on first line for align/baseline shift.
    let total_width: f32 = buffer
        .layout_runs()
        .next()
        .map(|run| run.line_w)
        .unwrap_or(0.0);

    let align_dx = match opts.align {
        crate::canvas2d::TextAlign::Start | crate::canvas2d::TextAlign::Left => 0.0,
        crate::canvas2d::TextAlign::End | crate::canvas2d::TextAlign::Right => -total_width,
        crate::canvas2d::TextAlign::Center => -total_width * 0.5,
    };

    // Baseline shift relative to `opts.y`. cosmic-text positions glyphs
    // such that y=0 is the top of the line box; we want the
    // alphabetic baseline at `opts.y` per canvas spec.
    //
    // Query the real ascent-to-em ratio from the primary (first shaped)
    // font instead of assuming 0.8 — different families place the
    // alphabetic baseline differently, and a fixed guess misplaces text
    // for any font whose ascent != 0.8em. Falls back to 0.8 if the font
    // can't be inspected.
    let primary_font_id = buffer
        .layout_runs()
        .next()
        .and_then(|run| run.glyphs.first().map(|g| g.physical((0.0, 0.0), 1.0).cache_key.font_id));
    let ascent_em = primary_font_id
        .and_then(|fid| fs.get_font(fid))
        .and_then(|font| {
            FontRef::from_index(font.data(), 0).map(|fr| {
                let m = fr.metrics(&[]);
                if m.units_per_em > 0 {
                    m.ascent / m.units_per_em as f32
                } else {
                    0.8
                }
            })
        })
        .unwrap_or(0.8);
    let baseline_dy = match opts.baseline {
        crate::canvas2d::TextBaseline::Top => 0.0,
        crate::canvas2d::TextBaseline::Hanging => -ascent_em * parsed.size_px * 0.2,
        crate::canvas2d::TextBaseline::Middle => -ascent_em * parsed.size_px * 0.5,
        crate::canvas2d::TextBaseline::Alphabetic => -ascent_em * parsed.size_px,
        crate::canvas2d::TextBaseline::Ideographic => -ascent_em * parsed.size_px * 1.05,
        crate::canvas2d::TextBaseline::Bottom => -parsed.size_px,
    };

    let mut scaler_ctx = ScaleContext::new();
    let pre_alpha_color = pre_alpha(opts.fill, opts.global_alpha);
    let world =
        opts.transform.post_translate(opts.x + align_dx, opts.y + baseline_dy);

    // Glyph blitting is source-over only. To honor any other
    // globalCompositeOperation, render the run onto a transparent scratch
    // pixmap with source-over, then composite that whole layer onto the
    // target with the requested blend mode (same approach the shape ops in
    // canvas2d.rs use). source-over (the common case) blits in place.
    let mut layer = if opts.composite == BlendMode::SourceOver {
        None
    } else {
        Some(
            Pixmap::new(pix.width(), pix.height())
                .ok_or_else(|| anyhow!("alloc text composite layer"))?,
        )
    };
    let target: &mut Pixmap = match layer.as_mut() {
        Some(l) => l,
        None => pix,
    };

    for run in buffer.layout_runs() {
        for glyph in run.glyphs.iter() {
            let phys = glyph.physical((0.0, 0.0), 1.0);
            let font = match fs.get_font(phys.cache_key.font_id) {
                Some(f) => f,
                None => continue,
            };
            let font_ref = match FontRef::from_index(font.data(), 0) {
                Some(f) => f,
                None => continue,
            };
            let mut scaler = scaler_ctx
                .builder(font_ref)
                .size(parsed.size_px)
                .hint(true)
                .build();
            let image = Render::new(&[
                Source::ColorOutline(0),
                Source::ColorBitmap(StrikeWith::BestFit),
                Source::Outline,
            ])
            .format(Format::Alpha)
            .offset(Vector::new(0.0, 0.0))
            .render(&mut scaler, phys.cache_key.glyph_id);
            let image = match image {
                Some(img) => img,
                None => continue,
            };
            blit_alpha_mask(
                target,
                world,
                glyph.x + phys.cache_key.x_bin.as_float() + image.placement.left as f32,
                run.line_y + glyph.y - image.placement.top as f32,
                image.placement.width as i32,
                image.placement.height as i32,
                &image.data,
                pre_alpha_color,
            );
        }
    }

    // If we rendered onto a scratch layer, composite it with the requested
    // blend mode now.
    if let Some(layer) = layer {
        let paint = tiny_skia::PixmapPaint {
            blend_mode: opts.composite,
            ..Default::default()
        };
        pix.draw_pixmap(0, 0, layer.as_ref(), &paint, Transform::identity(), None);
    }
    Ok(())
}

pub fn draw_stroke_text(pix: &mut Pixmap, opts: TextOptions<'_>) -> Result<()> {
    // For phase 1 we approximate stroke-text as fill-text (rare in fpjs
    // probe; can replace with path-stroke once Skia backend is in).
    draw_fill_text(pix, opts)
}

/* ---------- helpers ---------- */

#[derive(Debug, Clone)]
struct ParsedFont {
    size_px: f32,
    family: Option<String>,
    bold: bool,
    italic: bool,
}

/// Very small parser for the canvas CSS shorthand. Handles the shape
/// that fpjs and most pages use: "<weight>? <style>? <size>px <family>".
fn parse_font_string(s: &str) -> ParsedFont {
    let mut size_px = 10.0_f32;
    let mut family: Option<String> = None;
    let mut bold = false;
    let mut italic = false;
    let mut tokens = s.split_whitespace().peekable();
    while let Some(tok) = tokens.next() {
        let t = tok.to_ascii_lowercase();
        if t == "bold" || t == "700" || t == "800" || t == "900" {
            bold = true;
        } else if t == "italic" || t == "oblique" {
            italic = true;
        } else if let Some(px) = t.strip_suffix("px") {
            if let Ok(v) = px.parse::<f32>() {
                size_px = v;
            }
        } else if let Some(pt) = t.strip_suffix("pt") {
            if let Ok(v) = pt.parse::<f32>() {
                size_px = v * 96.0 / 72.0;
            }
        } else {
            // Everything past the size is the family name (which may
            // contain spaces / quotes / commas).
            let remainder: String = std::iter::once(tok.to_string())
                .chain(tokens.by_ref().map(|s| s.to_string()))
                .collect::<Vec<_>>()
                .join(" ");
            let clean = remainder
                .trim()
                .trim_matches(|c: char| c == '"' || c == '\'' || c == ',');
            // First family in the comma list wins.
            let first = clean.split(',').next().unwrap_or("");
            let first = first.trim().trim_matches(|c: char| c == '"' || c == '\'');
            if !first.is_empty() {
                family = Some(first.to_string());
            }
            break;
        }
    }
    ParsedFont { size_px, family, bold, italic }
}

fn pre_alpha(c: Color, alpha: f32) -> PremultipliedColorU8 {
    // Round all channels consistently (matches with_alpha in canvas2d.rs).
    let r = (c.red() * 255.0).round() as u8;
    let g = (c.green() * 255.0).round() as u8;
    let b = (c.blue() * 255.0).round() as u8;
    let a = (c.alpha() * alpha * 255.0).round() as u8;
    PremultipliedColorU8::from_rgba(
        ((r as u16 * a as u16) / 255) as u8,
        ((g as u16 * a as u16) / 255) as u8,
        ((b as u16 * a as u16) / 255) as u8,
        a,
    )
    .unwrap_or_else(|| {
        PremultipliedColorU8::from_rgba(0, 0, 0, 0).expect("transparent")
    })
}

/// Composite an 8-bit alpha mask onto the target pixmap using `color`
/// (already premultiplied). Honors the active transform's translate
/// component only — for the canvas2d probes fpjs runs (axis-aligned
/// text drawn at canvas-space coordinates) that's sufficient. Rotation
/// / scale propagate via the glyph layout positions, not the per-glyph
/// blit transform.
fn blit_alpha_mask(
    pix: &mut Pixmap,
    world: Transform,
    px: f32,
    py: f32,
    w: i32,
    h: i32,
    alpha: &[u8],
    color: PremultipliedColorU8,
) {
    if w <= 0 || h <= 0 {
        return;
    }
    // Transform glyph origin into pixmap-space. We respect the
    // translation + uniform-scale components of the current transform;
    // rotation propagates via the glyph layout positions rather than
    // per-glyph blit transforms (good enough for fpjs's
    // axis-aligned text probes).
    let mut p = tiny_skia::Point::from_xy(px, py);
    world.map_point(&mut p);
    let ox = p.x.round() as i32;
    let oy = p.y.round() as i32;
    let pmw = pix.width() as i32;
    let pmh = pix.height() as i32;

    // This blit is source-over only; non-source-over modes are handled by the
    // caller compositing a scratch layer (see draw_fill_text).
    let dst = pix.pixels_mut();
    for row in 0..h {
        let dy = oy + row;
        if dy < 0 || dy >= pmh {
            continue;
        }
        for col in 0..w {
            let dx = ox + col;
            if dx < 0 || dx >= pmw {
                continue;
            }
            let a = alpha[(row * w + col) as usize];
            if a == 0 {
                continue;
            }
            let scale = a as u16;
            let cr = (color.red() as u16 * scale) / 255;
            let cg = (color.green() as u16 * scale) / 255;
            let cb = (color.blue() as u16 * scale) / 255;
            let ca = (color.alpha() as u16 * scale) / 255;
            let dst_idx = (dy * pmw + dx) as usize;
            let d = dst[dst_idx];
            let inv = 255 - ca;
            let nr = (cr + (d.red() as u16 * inv) / 255).min(255) as u8;
            let ng = (cg + (d.green() as u16 * inv) / 255).min(255) as u8;
            let nb = (cb + (d.blue() as u16 * inv) / 255).min(255) as u8;
            let na = (ca + (d.alpha() as u16 * inv) / 255).min(255) as u8;
            dst[dst_idx] = PremultipliedColorU8::from_rgba(nr, ng, nb, na)
                .unwrap_or_else(|| {
                    PremultipliedColorU8::from_rgba(0, 0, 0, 0).expect("transparent")
                });
        }
    }
}

