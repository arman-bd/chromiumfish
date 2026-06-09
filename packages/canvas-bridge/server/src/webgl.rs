//! WebGL backend.
//!
//! Two compile-time variants:
//!   * default — stub. Accepts ops, returns the host's identity
//!     strings, refuses `readPixels`. Lets clients fall back to local
//!     rendering cleanly.
//!   * `--features webgl` — `glow` over a `surfman` headless GL context
//!     (ANGLE+D3D11 on Windows, CGL on macOS, EGL on Linux). Replays
//!     the WebGL command stream into a real GPU-backed framebuffer
//!     and returns raw pixels on `readPixels`.
//!
//! fpjs's WebGL fingerprint probe:
//!   1. createContextAttributes (alpha:true, depth:true, …)
//!   2. getParameter(GL_RENDERER, GL_VENDOR, GL_VERSION, …)
//!   3. getSupportedExtensions
//!   4. createBuffer / shader compile / link / draw a colored triangle
//!   5. readPixels(0, 0, 256, 128) → hash
//!
//! Reproducing step (5) byte-identical to real Win Chrome requires
//! the **same ANGLE backend** the server runs (D3D11). On Windows
//! that's straightforward; macOS/Linux servers will produce
//! platform-native WebGL output, which is the next-best identity to
//! ship (consistent host-platform pixels, but not Win-canonical).

use anyhow::{anyhow, Result};
use canvas_bridge_proto::{WebGLAttrs, WebGLOp};

pub struct WebGLContext {
    width: u32,
    height: u32,
    attrs: WebGLAttrs,
    /// 1 for WebGL1, 2 for WebGL2.
    version: u8,
    op_count: u64,

    #[cfg(feature = "webgl")]
    gl: Option<GlBackend>,
}

#[cfg(feature = "webgl")]
struct GlBackend {
    // Real backend lives in src/webgl_real.rs (compiled only with the
    // feature). Holds the surfman device + context + glow `Context`.
    inner: crate::webgl_real::Backend,
}

impl WebGLContext {
    pub fn new(width: u32, height: u32, attrs: WebGLAttrs, version: u8) -> Self {
        #[cfg(feature = "webgl")]
        let gl = crate::webgl_real::Backend::new(width, height, &attrs, version)
            .map_err(|e| {
                tracing::warn!(err = %e, "GL backend init failed; will refuse readPixels");
                e
            })
            .ok()
            .map(|inner| GlBackend { inner });

        Self {
            width,
            height,
            attrs,
            version,
            op_count: 0,

            #[cfg(feature = "webgl")]
            gl,
        }
    }

    pub fn replay(&mut self, op: WebGLOp) -> Result<()> {
        self.op_count += 1;
        #[cfg(feature = "webgl")]
        if let Some(b) = self.gl.as_mut() {
            return b.inner.replay(op);
        }
        let _ = op;
        Ok(())
    }

    pub fn read_pixels(
        &mut self,
        _x: i32,
        _y: i32,
        w: u32,
        h: u32,
        _format: u32,
        _ty: u32,
    ) -> Result<Vec<u8>> {
        #[cfg(feature = "webgl")]
        if let Some(b) = self.gl.as_mut() {
            return b.inner.read_pixels(_x, _y, w, h);
        }
        Err(anyhow!(
            "WebGL readPixels needs --features webgl; buffered {} ops",
            self.op_count
        ))
    }

    pub fn query_strings(&self, keys: &[String]) -> Vec<String> {
        keys.iter()
            .map(|k| match k.as_str() {
                "GL_VERSION" if self.version == 2 => {
                    "WebGL 2.0 (OpenGL ES 3.0 Chromium)".into()
                }
                "GL_VERSION" => "WebGL 1.0 (OpenGL ES 2.0 Chromium)".into(),
                "GL_VENDOR" => "WebKit".into(),
                "GL_RENDERER" => "WebKit WebGL".into(),
                "GL_SHADING_LANGUAGE_VERSION" if self.version == 2 => {
                    "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Chromium)".into()
                }
                "GL_SHADING_LANGUAGE_VERSION" => {
                    "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)".into()
                }
                "GL_RENDERER_UNMASKED" => {
                    #[cfg(target_os = "windows")]
                    {
                        "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)".into()
                    }
                    #[cfg(target_os = "macos")]
                    {
                        "ANGLE (Apple, Apple M1, OpenGL 4.1)".into()
                    }
                    #[cfg(target_os = "linux")]
                    {
                        "ANGLE (Intel, Mesa Intel(R) UHD Graphics, OpenGL 4.6)".into()
                    }
                }
                _ => String::new(),
            })
            .collect()
    }

    #[allow(dead_code)]
    pub fn size(&self) -> (u32, u32) {
        (self.width, self.height)
    }

    #[allow(dead_code)]
    pub fn attrs(&self) -> WebGLAttrs {
        self.attrs
    }
}
