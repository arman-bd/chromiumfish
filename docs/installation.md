---
title: Installation
nav_order: 2
---

# Installation
{: .no_toc }

1. TOC
{:toc}

---

ChromiumFish ships as two packages that share one browser build. Both require
[Playwright](https://playwright.dev) and download the binary on first use.

## Python

```bash
pip install chromiumfish
```

Playwright is pulled in as a dependency. You do **not** need `playwright install` —
ChromiumFish brings its own browser.

Optionally pre-fetch the browser build (it also happens automatically on first launch):

```bash
chromiumfish fetch
```

This downloads and caches the build under `~/.cache/chromiumfish/<version>/`.

## Node

```bash
npm install chromiumfish playwright-core
```

`playwright-core` is a peer dependency. Then optionally pre-fetch the build:

```bash
npx chromiumfish fetch
```

## Configuration

| Environment variable | Purpose |
|----------------------|---------|
| `CHROMIUMFISH_VERSION` | Pin a specific browser build version. |
| `CHROMIUMFISH_CACHE_DIR` | Override the cache location. |

## Platform support

| Platform | Status |
|----------|--------|
| Linux x64 | ✅ Supported (SwiftShader, headless-friendly) |
| Windows x64 | 🧪 Planned |
| macOS arm64 | 🧪 Planned |

{: .note }
> Linux builds run on GPU-less hosts via SwiftShader, which is ideal for cloud/VPS
> automation.
