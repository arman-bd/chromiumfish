---
title: Personas
nav_order: 6
---

# Personas
{: .no_toc }

1. TOC
{:toc}

---

A **persona** is the complete, self-consistent fingerprint ChromiumFish presents:
user-agent, Client Hints, WebGL vendor/renderer string, fonts, audio, screen metrics,
and more. Every persona is derived deterministically from a single string, the
**`persona_seed`**. Any stable string works as the id: a numeric string is used as-is, and
any other string is hashed to a stable persona, so different strings give different
personas. Omit it and you get the build's default persona.

All of this is produced in the browser engine itself, not by JavaScript patches injected
at runtime. The SDK passes the seed through to the build and nothing more.

## The core idea

One seed produces one coherent fingerprint, and the same seed always produces the same one.

- **Same seed, same persona.** Re-running with `persona_seed="alpha-7"` reproduces the exact
  same persona every time. That is what you want for cross-session continuity: the site
  sees a returning visitor, not a new device on every request.
- **Different seed, uncorrelated persona.** Change the seed and the surfaces change
  together, consistently. On non-Mac builds the per-seed audio offset differs between
  seeds, so two personas don't share an audio hash.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

# Account A: always this identity
with Chromiumfish(persona_seed="alice") as browser:
    ...

# Account B: a different, uncorrelated identity
with Chromiumfish(persona_seed="bob") as browser:
    ...
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const a = await ChromiumFish({ personaSeed: "alice" });
// ... use a ...
await a.close();

const b = await ChromiumFish({ personaSeed: "bob" });
// ... use b ...
await b.close();
```

## Choosing ids

- **Use a stable id per account or profile.** Any string works, so the account's own id is
  often all you need. The same id always rebuilds the same persona.
- **Rotate ids for anonymity.** For one-off scrapes you don't want linked together, use a
  fresh random string each run.
- **Keep network and persona aligned.** A persona's locale and timezone should match its
  exit IP. Pair ids with proxies deliberately, and let `timezone="auto"` resolve the
  egress IP's zone if you don't want to set it by hand.

Because the id is just a string, the account id itself can be the persona id. There's no
separate seed table to keep:

```python
from chromiumfish.sync_api import Chromiumfish

def scrape(account_id: str):
    with Chromiumfish(persona_seed=account_id) as browser:
        page = browser.new_page()
        page.goto("https://example.com/account")
        return page.title()
```

{: .warning }
> A persona spoofs the **browser fingerprint**, not your network identity. IP reputation,
> TLS, and behaviour still matter. For high-friction targets, combine a persona with a
> clean residential proxy and human-like interaction.

## Mobile and OS persona

By default a persona presents as **Windows** desktop Chrome. `--persona-os` switches the
whole OS family the persona claims — not just the User-Agent, but the coherent stack behind
it (Client Hints and `Sec-CH-UA-Platform`, and OS-specific engine behaviour such as the
math/`libm` results, the outbound TCP TTL, and the media key systems). Pass it through the
SDK's `args` list:

| Value | Persona |
|-------|---------|
| `win` | Windows desktop Chrome. **Default** — used when the flag is absent. |
| `mac` | macOS desktop Chrome. |
| `android` | A seed-driven **Pixel-family phone**: mobile UA + Client Hints, phone screen metrics and DPR, touch, mobile viewport, a Mali WebGL string, and `pointer: coarse` / `hover: none`. |

Like the desktop persona, the mobile one is **seed-driven**: the `persona_seed` picks the
specific device out of the Pixel pool, so the same seed always reproduces the same phone.

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(
    persona_seed="alpha-7",
    args=["--persona-os=android"],
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")   # navigator.userAgentData.mobile === true
```

```javascript
const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  args: ["--persona-os=android"],
});
```

{: .warning }
> **The Android persona is functional but not airtight.** The UA, Client Hints, screen,
> touch, and WebGL surfaces are coherent and were verified byte-exact against a real Pixel,
> but residual tells remain — the font set, exact-match canvas pixels, and locale/timezone
> alignment are not fully mobile. For the strictest anti-fingerprinting targets, prefer the
> default desktop persona; if you do use `android`, pair it with a mobile-region proxy and a
> matching `timezone`/locale, and don't lean on it against the hardest detectors.

## Canvas and WebGL (optional bridge)

The WebGL vendor/renderer **string** is part of the persona and reports a real D3D11/ANGLE
GPU, with no Apple or Metal leakage. The **pixels** are a separate matter.

By default, canvas and WebGL pixel reads (`toDataURL`, `getImageData`, `readPixels`,
`measureText`) pass through clean. On a headless Linux build that means SwiftShader's
software output. There is no in-engine canvas noise and no per-seed canvas isolation, so
two seeds can produce the same canvas hash.

If you need those reads to look like a real GPU, ChromiumFish supports an optional
**canvas-bridge**: a separate render service running on a Windows machine. When the build
is pointed at the bridge (two command-line flags passed through the SDK's `args` list),
those reads are answered by the real Windows renderer instead of local SwiftShader. See
[Canvas & WebGL bridge](canvas-bridge) for the full setup.

## Geolocation (GPS)

A persona can also carry a **fixed GPS location**. Give it a latitude/longitude pair and
ChromiumFish does two things at once:

- **Auto-grants** the Geolocation permission for the session — no prompt, and
  `navigator.permissions.query({ name: "geolocation" })` reports `granted`.
- **Overrides** the Geolocation API session-wide. Every frame, current and future, reports
  the spoofed position, and the browser never subscribes to the real network/system location
  providers. It's the engine-level equivalent of CDP's `Emulation.setGeolocationOverride`.

Set it with command-line flags passed through the SDK's `args` list (Python `args=`,
Node `args:`):

| Flag | Required | Description |
|------|----------|-------------|
| `--persona-lat=<deg>` | yes | Latitude in decimal degrees. |
| `--persona-lng=<deg>` | yes | Longitude in decimal degrees. |
| `--persona-accuracy=<m>` | no | Horizontal accuracy in meters. Defaults to `40`, a plausible GPS value. |

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(
    persona_seed="alpha-7",
    args=["--persona-lat=48.8584", "--persona-lng=2.2945"],  # Eiffel Tower
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  args: ["--persona-lat=48.8584", "--persona-lng=2.2945"],  // Eiffel Tower
});
const page = await browser.newPage();
await page.goto("https://example.com");
```

Unlike the fingerprint surfaces, the location is **explicit, not derived from the seed** —
you set the exact coordinates you want. Keep it coherent with the rest of the identity: a
GPS fix in Paris behind a US proxy on `America/New_York` is a contradiction a site can catch.
Pair it with a matching proxy and `timezone="auto"`.

## What's deterministic per seed

| Surface | Behaviour |
|---------|-----------|
| User-Agent + Client Hints | Coherent desktop persona, consistent across UA and high-entropy hints |
| WebGL vendor/renderer string | Reports a real D3D11/ANGLE GPU string; no Apple/Metal leakage |
| Canvas / WebGL pixels | Pass through clean by default; hardened only when the optional canvas-bridge is configured (see above) |
| Audio | Per-seed offset on non-Mac builds, below perceptual threshold |
| Fonts | Windows font set present; host fonts hidden |
