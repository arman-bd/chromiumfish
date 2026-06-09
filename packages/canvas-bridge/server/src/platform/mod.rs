//! Platform-specific stubs. Currently empty — `session::platform_info`
//! handles the per-OS identity strings via cfg attributes directly.
//! When the WebGL backend lands, this is where per-OS GL context
//! creation (WGL / EAGL / GLX or ANGLE-equivalent) will live.

#[allow(dead_code)]
pub fn placeholder() {}
