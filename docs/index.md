---
title: Home
layout: home
nav_order: 1
---

# ChromiumFish
{: .fs-9 }

A fingerprint-hardened Chromium fork that presents a coherent, consistent browser persona — with a drop-in Playwright harness for Python and Node.
{: .fs-6 .fw-300 }

[Get started](installation){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View on GitHub](https://github.com/arman-bd/chromiumfish){: .btn .fs-5 .mb-4 .mb-md-0 }

---

Unlike JavaScript-patch stealth libraries, the spoofing is done **natively in the engine
(C++)**. There are no `Function.prototype.toString` tampering tells, `navigator.webdriver`
is `false` even under CDP, and there are no `cdc_` automation artifacts.

This site documents the **`chromiumfish` SDKs** — the `pip` and `npm` packages that
download the matching browser build and launch it through
[Playwright](https://playwright.dev) with familiar, drop-in ergonomics.

## Why ChromiumFish

- **Native spoofing.** User-Agent, Client Hints, WebGL (reports D3D11/ANGLE on Intel, no
  Apple/Metal tells), fonts, audio, and canvas are spoofed in the engine — coherent and
  tamper-free.
- **Per-seed personas.** One `persona_seed` produces one stable, internally consistent
  identity. Reuse it for continuity, rotate it for a fresh, uncorrelated persona.
- **Self-contained.** Per-seed canvas/WebGL isolation ships as a bundled addon, with no
  external service to run.
- **It's just Chromium.** Everything you know about Playwright applies; the SDK is a thin
  wrapper over `chromium.launch(executablePath=…)`.

## How distribution works

The browser is built privately and published as **GitHub Release assets** on the public
[`arman-bd/chromiumfish`](https://github.com/arman-bd/chromiumfish) repo. On first use, the
SDK resolves `version → platform asset`, verifies its SHA-256, extracts it to
`~/.cache/chromiumfish/<version>/`, and hands the path to Playwright.

## Next steps

- [Installation](installation) — add ChromiumFish to a Python or Node project.
- [Quickstart](quickstart) — launch a stealth browser in five lines.
- [Personas](personas) — stable, rotatable identities via `persona_seed`.
- [API Reference](api) — full options for both SDKs.

{: .warning }
> **Disclaimer.** ChromiumFish is provided for **educational and authorized research
> purposes only**. You are solely responsible for how you use it, and must comply with all
> applicable laws and the terms of service of any site or service you interact with. The
> software is provided "as is", without warranty of any kind; to the maximum extent
> permitted by law, the author and contributors accept no liability for any damage or loss
> arising from its use or misuse.

{: .note }
> ChromiumFish is an independent fork of the [Chromium](https://www.chromium.org/) project
> and is not affiliated with or endorsed by Google.
