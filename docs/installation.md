---
title: Installation
nav_order: 2
---

# Installation
{: .no_toc }

1. TOC
{:toc}

---

ChromiumFish ships as two packages that share one private browser build. Both use
[Playwright](https://playwright.dev) and download the binary on first use. The SDK
itself has no fingerprinting logic; it fetches, verifies, and caches the build, then
launches it through Playwright.

## Python

```bash
pip install chromiumfish
```

Playwright is pulled in as a dependency. You do **not** need `playwright install`;
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
| `CHROMIUMFISH_CACHE_DIR` | Override the cache location (default `~/.cache/chromiumfish/<version>/`). |
| `CHROMIUMFISH_GEOIP_VERSION` | Pin the ip2tz database version (e.g. `2026.06`) or `latest`. |
| `CHROMIUMFISH_GEOIP_TTL` | How often to re-check the `latest` ip2tz pointer. |

{: .note }
> Using `timezone="auto"` downloads a small ip2tz database on first use, so that
> call needs network access. The DB caches after the first download.

## Platform support

| Platform | Status |
|----------|--------|
| Linux x64 | Supported (SwiftShader, headless-friendly) |
| macOS arm64 (Apple Silicon) | Supported |
| Windows x64 | Coming soon |

{: .note }
> Linux builds run on GPU-less hosts via SwiftShader, which is ideal for cloud/VPS
> automation.
