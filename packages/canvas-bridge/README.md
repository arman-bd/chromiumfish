# canvas-bridge

Remote canvas / WebGL / font rendering for ChromiumFish. Lets a ChromiumFish
instance on macOS (or Linux) forward its canvas2d ops, WebGL draw calls, and
font-metric probes to a server running on a real Windows host, so the pixel
bytes and metric numbers that come back are **actually produced by Windows
DirectWrite / D3D11 / Skia** — not spoofed.

Why? Spoofing Win-Chrome output on a Mac creates inconsistencies (e.g.
SwiftShader WebGL output that claims to be AMD D3D11, or font hashes baked
from one machine that don't match the local OS's fallback chain). Real Win
output has none of those tells, because it really is real Win output.

> **Standalone, optional, Windows-only service.** This lives in the
> ChromiumFish fork repo under `packages/canvas-bridge/` for convenience, but
> it is **not** part of the browser build and never starts automatically. You
> install and run the server yourself on a separate **Windows** host — that is
> the whole point, since only a Windows host returns real Windows bytes.
> ChromiumFish (on macOS or Linux) only talks to it when you pass
> `--canvas-bridge-url`; with that flag absent, the browser behaves exactly as
> it does today (local Skia path).

## Architecture

```
ChromiumFish (macOS / Linux)            canvas-bridge-server (Windows)
┌──────────────────────────┐            ┌─────────────────────────────────┐
│ Blink canvas2d / WebGL   │            │ WebSocket listener (TLS, basic  │
│ patched to forward ops   │            │ auth) — accepts one session per │
│ when --canvas-bridge-url │            │ peer.                           │
│ is set; otherwise no-op  │            │                                 │
│                          │  WSS +     │ Session dispatcher              │
│ Per-canvas op buffer →   │  msgpack ──▶  ├─ canvas2d replay (Skia)     │
│ flush on toDataURL /     │            │  ├─ webgl replay (ANGLE/GL)    │
│ getImageData /           │  ◀──────── │  └─ font metrics (DirectWrite, │
│ readPixels               │  PNG/raw   │      CoreText, or FontConfig)  │
└──────────────────────────┘  bytes     └─────────────────────────────────┘
```

## Project layout

```
packages/canvas-bridge/
├── proto/    — wire protocol (msgpack message types), shared lib
├── server/   — Rust render server, runs on Win / Mac / Linux
├── client/   — patches + docs for ChromiumFish-side integration
└── tools/    — test client, benchmarks, bridge-vs-Chrome equivalence check
```

## Install (Windows)

**The server is installed and run on Windows.** That is the entire point: it
returns the real bytes of the Windows graphics stack — DirectWrite text,
D3D11/Mesa GL, the Windows font fallback chain. Run it anywhere else and you
get *that* platform's bytes, which is useless for matching Windows Chrome. A
non-Windows server is therefore only ever a development smoke-test (see
[Development on macOS / Linux](#development-on-macos--linux-testing-only)),
never a deployment.

### Prerequisites

| Toolchain | Build | Runtime |
|---|---|---|
| **MSVC** | Rust 1.74+, VS 2022 Build Tools (C++ workload) | Mesa3D `opengl32.dll` + `libEGL.dll` next to the exe (only for `--features webgl` on GPU-less hosts, e.g. a VPS) |
| **GNU** | Rust 1.74+, MinGW-w64 with binutils on PATH (`dlltool.exe` is required by `libloading 0.8.9`) | same Mesa DLLs as MSVC |

The WebGL backend loads `libEGL.dll` dynamically on the first WebGL request,
so on a GPU-less Windows host Mesa3D's `libEGL.dll` + `opengl32.dll` must sit
next to `canvas-bridge-server.exe` (see `releases/` notes). Without
`--features webgl` the server uses the WebGL stub and needs no Mesa DLLs.

### Build & run

```bat
git clone https://github.com/arman-bd/chromiumfish.git
cd chromiumfish\packages\canvas-bridge
cargo build --release --features webgl -p canvas-bridge-server

target\release\canvas-bridge-server.exe ^
    --listen 0.0.0.0:8443 ^
    --auth user:secret ^
    --cert .\cert.pem --key .\key.pem
```

Pin the listen port in Windows Firewall, or run it behind Tailscale / an SSH
tunnel (TLS is phase-2 — see Status).

## Connect a browser to it

The browser side is just two command-line switches on the ChromiumFish binary
(recognized once the [client patches](client/patches/README.md) are applied and
the browser is rebuilt — see Status):

```
--canvas-bridge-url=wss://your-win-host:8443/render
--canvas-bridge-auth=user:secret
```

Pass them however you launch ChromiumFish. With the SDKs, forward them via the
`args` list:

```python
# Python
from chromiumfish.sync_api import Chromiumfish

browser = Chromiumfish(
    persona_seed="alpha-7",
    args=[
        "--canvas-bridge-url=wss://your-win-host:8443/render",
        "--canvas-bridge-auth=user:secret",
    ],
)
```

```javascript
// Node
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  args: [
    "--canvas-bridge-url=wss://your-win-host:8443/render",
    "--canvas-bridge-auth=user:secret",
  ],
});
```

With `--canvas-bridge-url` absent the browser ignores the bridge entirely and
renders locally (current behavior) — the bridge is strictly opt-in.

## Status

| Layer | Status |
|---|---|
| Wire protocol (msgpack, versioned) | ✅ shipped |
| WebSocket server + HTTP Basic auth | ✅ shipped |
| canvas2d ops (rects, paths, transforms, drawImage) — tiny-skia backend | ✅ byte-identical to Chrome's `getImageData` (proven via `tools/compare_with_chrome.py`) |
| canvas2d `fillText` / `strokeText` — cosmic-text + swash | ✅ renders, visually identical; AA fringes differ vs Skia (~7% pixel diff in text area) |
| canvas2d byte-exact text — real Skia (`skia-safe`) | ⏳ phase 2 swap |
| Font metric query (`MeasureText`) — host DirectWrite/CoreText/FontConfig via `font-kit` | ✅ shipped |
| WebGL — stub (identity strings, refuses readPixels) | ✅ shipped (default) |
| WebGL — real off-screen GL via dynamic `libEGL` + `glow` | ✅ shipped behind `--features webgl` (uses Mesa software GL on GPU-less hosts) |
| Blink-side client patches | ✅ written (`client/patches/`), application requires Chromium rebuild |
| TLS / WSS | ⏳ phase 2 (run behind SSH tunnel for now) |
| End-to-end equivalence test | ✅ `tools/compare_with_chrome.py` |

See `proto/src/lib.rs` for the wire format. See `client/patches/README.md`
for the patch set, file destinations, and `apply.sh` helper.

## Development on macOS / Linux (testing only)

You can build and run the server on macOS or Linux to exercise the wire
protocol and run the bridge-vs-Chrome equivalence check (see
[Verifying](#verifying)). **This renders with the host's graphics stack, so
the bytes are *not* Windows bytes — never point a real browser persona at a
non-Windows server.** It is for protocol development and CI only.

| OS | Build deps | WebGL (`--features webgl`) |
|---|---|---|
| **macOS** | Rust 1.74+, Xcode CLT (`xcode-select --install`) | unavailable — system EGL/GLES is absent on macOS; use the stub backend |
| **Linux** | Rust 1.74+, `pkg-config`, `libfontconfig1-dev`, `libfreetype-dev`; add `libegl1-mesa-dev` for webgl | loads system Mesa `libEGL.so.1`; runtime needs `libfontconfig1 libfreetype6 libegl1 libgles2 libgbm1` |

```bash
# Debian/Ubuntu dev box, in one shot:
sudo apt update && sudo apt install -y \
    build-essential pkg-config \
    libfontconfig1-dev libfreetype-dev \
    libegl1-mesa-dev libgles2-mesa-dev
cargo build --release --features webgl -p canvas-bridge-server
```

## Verifying

Local round-trip + equivalence check (runs on any dev OS):

```sh
# Terminal A — server:
cd packages/canvas-bridge
cargo run --release -- --listen 127.0.0.1:8443 --auth user:secret

# Terminal B — round-trip smoke test:
python3 tools/test_client.py ws://127.0.0.1:8443 user:secret
open /tmp/canvas_bridge_test.png

# Terminal B — bridge-vs-Chrome equivalence (requires Google Chrome installed):
python3 tools/compare_with_chrome.py
# expected: "MATCH — canvas-bridge output is byte-identical to Chrome's getImageData"
```

## Phase-2 work

1. **Real Skia backend** for byte-exact `fillText` pixel match. Swap
   `tiny-skia` for `skia-safe` (Chromium's actual Skia, exposed via
   Rust FFI). Keeps the rest of the codebase intact since the public
   API in `canvas2d.rs` (`Canvas2DContext::replay`, `image_data`,
   `encode`) is already trait-shaped.
2. **WebGL replay**: finish `webgl_real::Backend` op coverage (attribute
   binding tables, uniform setters, texture upload, FBO management).
   The context creation is done — `khronos-egl` + dynamic `libEGL`,
   software GL via Mesa on hosts without a GPU. Build with
   `cargo build --features webgl`.
3. **TLS**: `rustls` is already a dependency; wire `--cert` and `--key`
   in `main.rs`.
4. **Blink integration**: implement `CanvasBridgeClient::DoConnect`
   (raw TCP + WebSocket framing) and the per-op Send hooks in
   `base_rendering_context_2d.cc`. Patches in `client/patches/` show
   exactly where the calls land.

## Authors

Arman Hossain &lt;arman@bytetunnels.com&gt; · [github.com/arman-bd](https://github.com/arman-bd)
