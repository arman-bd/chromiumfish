---
title: Personas
nav_order: 4
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

## What's deterministic per seed

| Surface | Behaviour |
|---------|-----------|
| User-Agent + Client Hints | Coherent desktop persona, consistent across UA and high-entropy hints |
| WebGL vendor/renderer string | Reports a real D3D11/ANGLE GPU string; no Apple/Metal leakage |
| Canvas / WebGL pixels | Pass through clean by default; hardened only when the optional canvas-bridge is configured (see above) |
| Audio | Per-seed offset on non-Mac builds, below perceptual threshold |
| Fonts | Windows font set present; host fonts hidden |
