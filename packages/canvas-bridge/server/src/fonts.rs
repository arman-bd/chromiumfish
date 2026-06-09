//! Font metric queries via the host's native text stack.
//!
//! Resolves family names against the host's actual font database
//! (DirectWrite on Windows, CoreText on macOS, FontConfig on Linux)
//! via `font-kit`, then measures the rendered text using each face's
//! own metrics tables. fpjs's font_preferences hash hashes these
//! widths, so producing them from the *real* Win/Mac/Linux font
//! database is what makes the resulting hash trustworthy.

use anyhow::{anyhow, Result};
use canvas_bridge_proto::TextMetric;
use font_kit::family_name::FamilyName;
use font_kit::handle::Handle;
use font_kit::properties::Properties;
use font_kit::source::SystemSource;

pub fn measure(
    text: &str,
    families: &[String],
    sizes_px: &[f32],
) -> Result<Vec<Vec<TextMetric>>> {
    let src = SystemSource::new();

    let mut out = Vec::with_capacity(families.len());
    for family in families {
        let handle = src
            .select_best_match(
                &[
                    FamilyName::Title(family.clone()),
                    FamilyName::SansSerif,
                ],
                &Properties::new(),
            )
            .map_err(|e| anyhow!("font lookup '{family}': {e}"))?;
        let font = match handle {
            Handle::Path { path, font_index } => {
                font_kit::font::Font::from_path(&path, font_index)
                    .map_err(|e| anyhow!("font load '{family}': {e}"))?
            }
            Handle::Memory { bytes, font_index } => {
                font_kit::font::Font::from_bytes(bytes, font_index)
                    .map_err(|e| anyhow!("font load (memory) '{family}': {e}"))?
            }
        };
        let metrics = font.metrics();
        let units_per_em = metrics.units_per_em as f32;

        let mut row = Vec::with_capacity(sizes_px.len());
        for &size in sizes_px {
            let mut width = 0.0_f32;
            for ch in text.chars() {
                if let Some(glyph) = font.glyph_for_char(ch) {
                    let advance = font.advance(glyph).ok();
                    let dx = advance.map(|v| v.x()).unwrap_or(0.0);
                    width += dx / units_per_em * size;
                }
            }
            row.push(TextMetric {
                width,
                actual_bounding_box_ascent: metrics.ascent / units_per_em * size,
                actual_bounding_box_descent:
                    -metrics.descent / units_per_em * size,
                font_bounding_box_ascent: metrics.ascent / units_per_em * size,
                font_bounding_box_descent:
                    -metrics.descent / units_per_em * size,
            });
        }
        out.push(row);
    }
    Ok(out)
}
