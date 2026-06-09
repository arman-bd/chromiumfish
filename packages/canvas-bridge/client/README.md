# canvas-bridge — ChromiumFish-side integration

The browser is **off by default**. Two new command-line flags turn it on:

| Flag | Purpose |
|---|---|
| `--canvas-bridge-url=wss://host:port/render` | Where the render server lives. If absent, the bridge code path is dormant and canvas/WebGL render locally as before. |
| `--canvas-bridge-auth=user:secret` | Credentials sent as HTTP Basic on the WebSocket upgrade. Required when `--canvas-bridge-url` is set. |

When both are present, the browser:

1. On first canvas or WebGL context creation per renderer, opens one
   persistent WSS to the server.
2. Sends `Hello { persona_seed }` and waits for `Welcome`.
3. For each `HTMLCanvasElement`, allocates a `CanvasId` and sends
   `CreateCanvas2D` / `CreateWebGL`.
4. As Blink dispatches canvas/WebGL ops, the bridge captures them and
   ships `Canvas2DOp` / `WebGLOp` messages.
5. When the page calls `toDataURL`, `getImageData`, or `readPixels`,
   the bridge flushes pending ops, sends a `GetCanvas2DPng` /
   `GetCanvas2DImageData` / `WebGLReadPixels` request, blocks on the
   reply, and returns the resulting bytes back into Blink.

## Blink hook points (planned, not yet patched)

- `third_party/blink/renderer/core/html/canvas/html_canvas_element.cc`
  - `ToDataURLInternal` → forward to bridge if active
  - `getImageData` callers → forward
- `third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc`
  - Every public draw method (`fillRect`, `fillText`, `drawImage`, …)
    appends to the per-canvas op buffer.
- `third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc`
  - Every GL call mirrored into the bridge's `WebGLOp` log.
  - `readPixels` flushes + reads back from the server.
- `content/browser/...` content-shell startup: parse the two new
  command-line switches, push them to the renderer via
  `RenderProcessHostImpl::AppendRendererCommandLine`.

## Failure mode

If the bridge is configured but the server is unreachable, **the
browser falls back to local rendering** rather than crashing the
tab. The patch logs a `[canvas-bridge] disabled: <reason>` line to
stderr and disables itself for the rest of the process lifetime.

## Privacy / threat model

The render server sees:

- All canvas/WebGL op streams the browser issues (i.e. every draw
  the page makes). This is normally never observable off-device;
  shipping it over the network means treating the server with the
  same trust you'd give a remote rendering service.
- The persona seed (so it can keep per-persona state isolated).

It does **not** see:

- HTML, cookies, storage, or anything outside the canvas/WebGL surface.
- Image *sources* in `drawImage` calls — those are streamed inline as
  PNG bytes only after the renderer has already loaded them; the
  server never makes its own HTTP requests.

Use TLS (`wss://`) and a non-guessable shared secret. Run the server
on a private VLAN if possible.
