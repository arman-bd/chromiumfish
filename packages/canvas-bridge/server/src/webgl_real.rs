//! Real WebGL backend — only compiled with `--features webgl`.
//!
//! Owns one EGL display + pbuffer surface + GLES2/3 context per
//! `WebGLContext`, and a `glow::Context` adapter on top for op replay.
//!
//! We dynamically load libEGL (Mesa3D ships `libEGL.dll` + `opengl32.dll`
//! /`libGLESv2.dll` next to our exe on Windows; system libEGL on Linux).
//! EGL pbuffers give a fully headless, GPU-less GLES context — exactly
//! what we need on the VPS where the prior surfman/WGL+DX11 path
//! required `WGL_NV_DX_interop` (an NVIDIA WGL extension Mesa lacks).
//!
//! Threading: GL contexts are not Send. We pin each WebGL context to
//! the I/O thread of the session — that's where ops arrive anyway.
//! Sessions are owned by one tokio task, so this works out by
//! construction.

#![cfg(feature = "webgl")]

use anyhow::{anyhow, Result};
use canvas_bridge_proto::{WebGLAttrs, WebGLOp};
use std::collections::HashMap;
use std::sync::OnceLock;

use khronos_egl as egl;
use glow::HasContext;

type Egl = egl::DynamicInstance<egl::EGL1_4>;

// Process-wide EGL instance — libEGL is loaded once. Mesa's libEGL.dll
// is preferred (sits next to the exe on the Win VPS); on other hosts
// we fall back to the system library name.
fn egl_instance() -> Result<&'static Egl> {
    static INSTANCE: OnceLock<Egl> = OnceLock::new();
    if let Some(e) = INSTANCE.get() {
        return Ok(e);
    }
    #[cfg(target_os = "windows")]
    let candidates: &[&str] = &["libEGL.dll", "EGL.dll"];
    #[cfg(target_os = "macos")]
    let candidates: &[&str] = &["libEGL.dylib"];
    #[cfg(target_os = "linux")]
    let candidates: &[&str] = &["libEGL.so.1", "libEGL.so"];

    let mut last = String::new();
    for name in candidates {
        match unsafe { Egl::load_required_from_filename(name) } {
            Ok(inst) => {
                let _ = INSTANCE.set(inst);
                return Ok(INSTANCE.get().unwrap());
            }
            Err(e) => last = format!("{name}: {e}"),
        }
    }
    Err(anyhow!("could not load libEGL ({})", last))
}

pub struct Backend {
    display: egl::Display,
    context: egl::Context,
    surface: egl::Surface,
    gl: glow::Context,
    #[allow(dead_code)]
    width: u32,
    #[allow(dead_code)]
    height: u32,
    fbo: glow::Framebuffer,

    /// Map WebGL client-side handles → native GL ids.
    programs: HashMap<u32, glow::Program>,
    shaders: HashMap<u32, glow::Shader>,
    buffers: HashMap<u32, glow::Buffer>,
}

impl Backend {
    pub fn new(width: u32, height: u32, _attrs: &WebGLAttrs, version: u8) -> Result<Self> {
        let egl = egl_instance()?;

        let renderable_bit = if version >= 2 {
            egl::OPENGL_ES3_BIT
        } else {
            egl::OPENGL_ES2_BIT
        };
        let config_attrs = [
            egl::SURFACE_TYPE, egl::PBUFFER_BIT,
            egl::RENDERABLE_TYPE, renderable_bit,
            egl::RED_SIZE, 8,
            egl::GREEN_SIZE, 8,
            egl::BLUE_SIZE, 8,
            egl::ALPHA_SIZE, 8,
            egl::DEPTH_SIZE, 24,
            egl::STENCIL_SIZE, 8,
            egl::NONE,
        ];
        let ctx_attrs = [
            egl::CONTEXT_CLIENT_VERSION, if version >= 2 { 3 } else { 2 },
            egl::NONE,
        ];
        let surf_attrs = [
            egl::WIDTH, width as i32,
            egl::HEIGHT, height as i32,
            egl::NONE,
        ];

        // SAFETY: All khronos-egl 6.0 Instance methods are marked unsafe because
        // we hold no static guarantee that libEGL's globals are sane. In our
        // single-threaded I/O thread caller and process-wide OnceLock'd handle
        // these invariants are upheld.
        let (display, context, surface) = unsafe {
            let display = egl
                .get_display(egl::DEFAULT_DISPLAY)
                .ok_or_else(|| anyhow!("eglGetDisplay returned NULL"))?;
            egl.initialize(display)
                .map_err(|e| anyhow!("eglInitialize: {e:?}"))?;
            egl.bind_api(egl::OPENGL_ES_API)
                .map_err(|e| anyhow!("eglBindAPI(GLES): {e:?}"))?;
            let config = egl
                .choose_first_config(display, &config_attrs)
                .map_err(|e| anyhow!("eglChooseConfig: {e:?}"))?
                .ok_or_else(|| anyhow!("no matching EGL config"))?;
            let context = egl
                .create_context(display, config, None, &ctx_attrs)
                .map_err(|e| anyhow!("eglCreateContext: {e:?}"))?;
            let surface = egl
                .create_pbuffer_surface(display, config, &surf_attrs)
                .map_err(|e| anyhow!("eglCreatePbufferSurface: {e:?}"))?;
            egl.make_current(display, Some(surface), Some(surface), Some(context))
                .map_err(|e| anyhow!("eglMakeCurrent: {e:?}"))?;
            (display, context, surface)
        };

        let gl = unsafe {
            glow::Context::from_loader_function(|s| {
                // get_proc_address takes &str in khronos-egl 6.0.
                match egl.get_proc_address(s) {
                    Some(p) => p as *const _,
                    None => std::ptr::null(),
                }
            })
        };

        let (fbo, fb_size) = unsafe {
            let f = gl
                .create_framebuffer()
                .map_err(|e| anyhow!("create_framebuffer: {e}"))?;
            gl.bind_framebuffer(glow::FRAMEBUFFER, Some(f));
            let tex = gl
                .create_texture()
                .map_err(|e| anyhow!("create_texture: {e}"))?;
            gl.bind_texture(glow::TEXTURE_2D, Some(tex));
            gl.tex_image_2d(
                glow::TEXTURE_2D,
                0,
                glow::RGBA as i32,
                width as i32,
                height as i32,
                0,
                glow::RGBA,
                glow::UNSIGNED_BYTE,
                None,
            );
            gl.framebuffer_texture_2d(
                glow::FRAMEBUFFER,
                glow::COLOR_ATTACHMENT0,
                glow::TEXTURE_2D,
                Some(tex),
                0,
            );
            gl.viewport(0, 0, width as i32, height as i32);
            (f, (width, height))
        };

        Ok(Self {
            display,
            context,
            surface,
            gl,
            width: fb_size.0,
            height: fb_size.1,
            fbo,
            programs: HashMap::new(),
            shaders: HashMap::new(),
            buffers: HashMap::new(),
        })
    }

    fn make_current(&self) -> Result<()> {
        let egl = egl_instance()?;
        // SAFETY: see Backend::new.
        unsafe {
            egl.make_current(
                self.display,
                Some(self.surface),
                Some(self.surface),
                Some(self.context),
            )
        }
        .map_err(|e| anyhow!("eglMakeCurrent: {e:?}"))
    }

    pub fn replay(&mut self, op: WebGLOp) -> Result<()> {
        use WebGLOp::*;
        self.make_current()?;
        unsafe {
            self.gl.bind_framebuffer(glow::FRAMEBUFFER, Some(self.fbo));
            match op {
                ClearColor { r, g, b, a } => self.gl.clear_color(r, g, b, a),
                Clear { mask } => self.gl.clear(mask),
                Enable(cap) => self.gl.enable(cap),
                Disable(cap) => self.gl.disable(cap),
                Viewport { x, y, w, h } => self.gl.viewport(x, y, w, h),
                CreateProgram { handle } => {
                    let p = self
                        .gl
                        .create_program()
                        .map_err(|e| anyhow!("create_program: {e}"))?;
                    self.programs.insert(handle, p);
                }
                CreateShader { handle, ty } => {
                    let s = self
                        .gl
                        .create_shader(ty)
                        .map_err(|e| anyhow!("create_shader: {e}"))?;
                    self.shaders.insert(handle, s);
                }
                ShaderSource { shader, source } => {
                    if let Some(&s) = self.shaders.get(&shader) {
                        self.gl.shader_source(s, &source);
                    }
                }
                CompileShader { shader } => {
                    if let Some(&s) = self.shaders.get(&shader) {
                        self.gl.compile_shader(s);
                    }
                }
                AttachShader { program, shader } => {
                    if let (Some(&p), Some(&s)) =
                        (self.programs.get(&program), self.shaders.get(&shader))
                    {
                        self.gl.attach_shader(p, s);
                    }
                }
                LinkProgram { program } => {
                    if let Some(&p) = self.programs.get(&program) {
                        self.gl.link_program(p);
                    }
                }
                UseProgram { program } => {
                    let p = self.programs.get(&program).copied();
                    self.gl.use_program(p);
                }
                CreateBuffer { handle } => {
                    let b = self
                        .gl
                        .create_buffer()
                        .map_err(|e| anyhow!("create_buffer: {e}"))?;
                    self.buffers.insert(handle, b);
                }
                BindBuffer { target, buffer } => {
                    let b = self.buffers.get(&buffer).copied();
                    self.gl.bind_buffer(target, b);
                }
                BufferData { target, data, usage } => {
                    self.gl.buffer_data_u8_slice(target, &data, usage);
                }
                GetAttribLocation { .. } | EnableVertexAttribArray(_) => {
                    /* TODO: track + replay attribute bindings */
                }
                VertexAttribPointer {
                    index, size, ty, normalized, stride, offset,
                } => {
                    self.gl.vertex_attrib_pointer_f32(
                        index, size, ty, normalized, stride, offset,
                    );
                }
                DrawArrays { mode, first, count } => {
                    self.gl.draw_arrays(mode, first, count);
                }
                DrawElements { mode, count, ty, offset } => {
                    self.gl.draw_elements(mode, count, ty, offset);
                }
                Raw { name, .. } => {
                    return Err(anyhow!("WebGL Raw op '{name}' not modeled"));
                }
            }
        }
        Ok(())
    }

    pub fn read_pixels(
        &mut self,
        x: i32,
        y: i32,
        w: u32,
        h: u32,
    ) -> Result<Vec<u8>> {
        self.make_current()?;
        // w/h are untrusted; `w * h * 4` in u32 would wrap and undersize the
        // buffer that glReadPixels writes into. Size it with checked 64-bit
        // math and bound it (256 MiB — far above any real readback).
        const MAX_READ_PIXELS_BYTES: u64 = 256 * 1024 * 1024;
        let len = (w as u64)
            .checked_mul(h as u64)
            .and_then(|n| n.checked_mul(4))
            .ok_or_else(|| anyhow!("readPixels {w}x{h} overflows"))?;
        if len > MAX_READ_PIXELS_BYTES {
            return Err(anyhow!(
                "readPixels {w}x{h} ({len} bytes) exceeds {MAX_READ_PIXELS_BYTES}"
            ));
        }
        let mut out = vec![0u8; len as usize];
        unsafe {
            self.gl.bind_framebuffer(glow::FRAMEBUFFER, Some(self.fbo));
            self.gl.read_pixels(
                x,
                y,
                w as i32,
                h as i32,
                glow::RGBA,
                glow::UNSIGNED_BYTE,
                glow::PixelPackData::Slice(&mut out),
            );
        }
        Ok(out)
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        if let Ok(egl) = egl_instance() {
            // SAFETY: see Backend::new.
            unsafe {
                let _ = egl.make_current(self.display, None, None, None);
                let _ = egl.destroy_surface(self.display, self.surface);
                let _ = egl.destroy_context(self.display, self.context);
            }
        }
    }
}
