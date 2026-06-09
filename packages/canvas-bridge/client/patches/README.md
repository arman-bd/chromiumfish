# Blink-side integration patches

What goes where, for the `--canvas-bridge-url` / `--canvas-bridge-auth`
flags to actually do something.

```
blink_canvas_bridge/    new files to drop into Chromium source tree
diffs/                  unified diffs against upstream Chromium files
apply.sh                helper that does both
```

## File destinations inside Chromium

| Source under `blink_canvas_bridge/`          | Drop-in destination |
|----------------------------------------------|---------------------|
| `canvas_bridge_switches.h`                   | `src/components/canvas_bridge/public/canvas_bridge_switches.h` |
| `canvas_bridge_switches.cc`                  | `src/components/canvas_bridge/canvas_bridge_switches.cc` |
| `canvas_bridge_client.h`                     | `src/third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_client.h` |
| `canvas_bridge_client.cc`                    | `src/third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_client.cc` |
| `canvas_bridge_codec.h`                      | `src/third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_codec.h` |
| `canvas_bridge_codec.cc`                     | `src/third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_codec.cc` |
| `BUILD.gn`                                   | `src/third_party/blink/renderer/platform/canvas_bridge/BUILD.gn` |

## Diffs

| Patch                                        | Target file |
|----------------------------------------------|-------------|
| `01-add-switches.patch`                      | `src/content/public/common/content_switches.cc` (+`.h`) |
| `02-platform-build-gn.patch`                 | `src/third_party/blink/renderer/platform/BUILD.gn` |
| `03-canvas-element-hook.patch`               | `src/third_party/blink/renderer/core/html/canvas/html_canvas_element.cc` |
| `04-canvas-2d-context-hook.patch`            | `src/third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc` |

## Apply

```sh
cd /Users/armansmac2/Dev/chromium   # the fork repo root (canvas-bridge now lives here under packages/)
bash packages/canvas-bridge/client/patches/apply.sh src
```

The script copies new files in place, then `git apply`s the diffs against
the src tree.

## Design notes

* The bridge is a **per-renderer-process singleton.** Open one WebSocket
  per renderer; multiplex all canvases in that renderer onto it. This
  avoids creating a connection per page navigation.
* `HTMLCanvasElement` is given an opaque `bridge_canvas_id_` allocated
  at first paint. Op-buffer flushing happens lazily — every public 2D
  call appends to the per-canvas buffer; `toDataURL` /
  `getImageData` block on flush + readback.
* If the bridge is unconfigured **or** the configured server is
  unreachable, the patch is a no-op: every call falls through to the
  upstream local-render path. This is verified at boot — `IsEnabled()`
  returns `false` if either switch is missing or the WS connection
  failed.
* Sync-from-async problem: `toDataURL` is a synchronous JS API but our
  readback is network-bound. Two options:
    1. **Run a blocking flush on a dedicated I/O thread** — simplest;
       acceptable for fpjs's once-per-probe call rate. Renderer thread
       waits on a `base::WaitableEvent`. *Default for now.*
    2. Make the bridge promise-based and require pages to call a
       `canvas.bridgeFlush().then(...)` — clean but breaks compat
       with anything that uses native `toDataURL`. Not done.

## Browser → renderer wiring

The two new switches are read in the **browser process** at startup
and propagated to the renderer via
`RenderProcessHostImpl::AppendRendererCommandLine`. The renderer reads
them in `RendererBlinkPlatformImpl::CreateCanvasBridgeClient` (helper
added by patch 02).
