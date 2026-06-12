---
title: Canvas & WebGL bridge
nav_order: 5
---

# Canvas & WebGL bridge
{: .no_toc }

1. TOC
{:toc}

---

Most of a persona is produced inside the engine: User-Agent, Client Hints, the
WebGL vendor/renderer **string**, fonts, audio, and screen metrics all come back
coherent and tamper-free with nothing extra to run. **Canvas and WebGL pixels are
the exception.** They are the hardest signal to fake from a headless Linux box,
and by default ChromiumFish does not try to — it leaves them clean.

The **canvas-bridge** is an optional way to make those pixel reads look like a
real GPU. It is a **separate render service you run yourself on a Windows host**;
it is not part of the browser binary and never starts on its own.

## What's native vs. what needs the bridge

| Surface | How it's handled |
|---------|------------------|
| User-Agent, Client Hints | Native, in the engine |
| WebGL vendor/renderer **string** | Native — reports a real D3D11/ANGLE GPU, no Apple/Metal tells |
| Fonts, audio, screen, WebRTC | Native |
| Canvas/WebGL **pixels** (`toDataURL`, `getImageData`, `readPixels`, `measureText`) | **Clean by default.** Real-GPU output only when pointed at the bridge |

On a headless Linux build, "clean by default" means the pixels are SwiftShader's
software output. That's fine for most scraping; a determined fingerprinter that
hashes canvas/WebGL output can still tell it apart from a real GPU. That's the gap
the bridge closes.

{: .note }
> There is **no in-engine canvas noise and no per-seed canvas isolation**. Two
> different `persona_seed` values can produce the same canvas hash. Canvas
> *identity* comes from the bridge host, not from the seed.

## How it fits together

```
ChromiumFish (macOS / Linux)          canvas-bridge-server (Windows)
┌──────────────────────────┐          ┌──────────────────────────────┐
│ Blink canvas2d / WebGL    │   ws://  │ Renders the ops with the real │
│ forwards its ops only when │ ───────▶ │ Windows graphics stack        │
│ --canvas-bridge-url is set │ ◀─────── │ (DirectWrite / D3D11 / Skia)  │
│ otherwise renders locally  │  pixels  │ and returns the real bytes    │
└──────────────────────────┘          └──────────────────────────────┘
```

The point of running it on Windows is that it returns **the actual bytes of the
Windows graphics stack**. Run the server anywhere else and you get *that*
platform's bytes, which defeats the purpose — so a non-Windows server is only ever
a development smoke test, never a deployment.

## Turning it on

The browser side is two command-line switches. **Both are required** — the bridge
stays off unless `--canvas-bridge-url` *and* `--canvas-bridge-auth` are both set:

```
--canvas-bridge-url=ws://your-win-host:8443/render
--canvas-bridge-auth=user:secret
```

With the SDKs, pass them through the `args` list.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(
    persona_seed="alpha-7",
    args=[
        "--canvas-bridge-url=ws://your-win-host:8443/render",
        "--canvas-bridge-auth=user:secret",
    ],
) as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  args: [
    "--canvas-bridge-url=ws://your-win-host:8443/render",
    "--canvas-bridge-auth=user:secret",
  ],
});
const page = await browser.newPage();
await page.goto("https://abrahamjuliot.github.io/creepjs/");
```

Leave the switches out and the browser ignores the bridge entirely and renders
locally — the bridge is strictly opt-in.

{: .warning }
> **Use `ws://` over an encrypted tunnel.** TLS (`wss://`) isn't implemented in the
> browser-side client yet; if you pass a `wss://` URL it logs a warning and falls
> back to plaintext. Run the bridge over a Tailscale network or an SSH tunnel so
> the link is encrypted underneath, and don't expose the port to the open
> internet. Never put the bridge's host or credentials in code you publish.

## Running the server

The server lives in the fork repo under
[`packages/canvas-bridge/`](https://github.com/arman-bd/chromiumfish/tree/main/packages/canvas-bridge)
and ships with its own README covering the Windows build, the GPU-less WebGL path
(Mesa3D DLLs next to the exe), and the equivalence test against real Chrome. It is
a Rust service; build it with `cargo build --release --features webgl -p
canvas-bridge-server` and run it on the Windows host you want to borrow pixels
from.

See the [canvas-bridge README](https://github.com/arman-bd/chromiumfish/tree/main/packages/canvas-bridge)
for the full server setup, prerequisites, and current feature status.

## When you need it (and when you don't)

- **You probably don't need it** for ordinary scraping, content extraction, or
  sites that don't hash canvas/WebGL. The native persona already clears most bot
  walls; the [Quickstart](quickstart) flows never touch the bridge.
- **Reach for it** when a specific target reads canvas or WebGL pixels back and
  treats headless-Linux SwiftShader output as a tell. That's the one gap the
  native engine leaves open, and the bridge is how you close it.
