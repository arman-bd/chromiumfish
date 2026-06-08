---
title: Python API
parent: API Reference
nav_order: 1
---

# Python API
{: .no_toc }

1. TOC
{:toc}

---

```bash
pip install chromiumfish
```

No `playwright install` step. The SDK fetches and launches the browser build itself, then hands you a standard Playwright `Browser`.

## `Chromiumfish` (sync)

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed=27182, headless=True) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

A context manager that launches the browser and yields a Playwright
[`Browser`](https://playwright.dev/python/docs/api/class-browser). Closing the context
closes the browser and stops Playwright.

## `AsyncChromiumfish` (async)

```python
from chromiumfish.async_api import AsyncChromiumfish

async with AsyncChromiumfish(persona_seed=27182) as browser:
    page = await browser.new_page()
```

Same API, returns an async `Browser`.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `persona_seed` | `int` | none | Integer seed for a stable, internally consistent fingerprint persona. Omit for the build's default persona. |
| `headless` | `bool` | `True` | Run headless (SwiftShader). |
| `proxy` | `dict` | none | Playwright proxy dict: `{"server": ..., "username": ..., "password": ...}`. |
| `window_size` | `tuple` | `(1920, 1080)` | Window dimensions. Pass `None` to omit the flag. |
| `version` | `str` | none | Override the browser build version (defaults to the pinned build). |
| `download` | `bool` | `True` | Download the build automatically if it isn't cached. |
| `timezone` | `str` | `None` | `"auto"` resolves the egress IP's IANA timezone via the ip2tz DB and sets the browser TZ. An IANA string like `"Europe/Berlin"` is used verbatim. `None` disables timezone handling. |
| `args` | `list[str]` | none | Extra Chromium command-line flags. |
| `**launch_kwargs` | `Any` | none | Any other keyword arguments are forwarded to `chromium.launch()`. |

When you set a proxy, `timezone="auto"` reads the timezone from the proxy's egress IP, so the browser clock matches where the traffic actually comes from.

```python
with Chromiumfish(
    persona_seed=27182,
    proxy={"server": "http://proxy.example:8080"},
    timezone="auto",
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

## Timezone helpers

The same ip2tz lookup is available directly, so you can resolve a timezone without launching a browser.

```python
from chromiumfish import lookup_timezone, resolve_timezone

lookup_timezone("8.8.8.8")  # -> "America/Los_Angeles" (IANA str, or None)
resolve_timezone()          # -> your own egress IP's timezone
```

`lookup_timezone` returns an IANA string or `None` when the IP isn't in the DB. `resolve_timezone` looks up your current egress IP, which is what `timezone="auto"` uses internally.

The DB downloads once and caches. It tracks the monthly "latest" build and re-checks weekly. Pin a fixed version for reproducibility:

```bash
export CHROMIUMFISH_GEOIP_VERSION=2026.06
```

## Module functions

| Function | Description |
|----------|-------------|
| `fetch(version=None, *, force=False) -> Path` | Download and cache the build; returns the binary path. |
| `binary_path(version=None, *, download=True) -> Path` | Path to the cached binary, fetching if needed (and allowed). |
| `install_dir(version=None) -> Path` | The per-version install directory. |

## Environment variables

| Variable | Description |
|----------|-------------|
| `CHROMIUMFISH_VERSION` | Pin the browser build version. |
| `CHROMIUMFISH_CACHE_DIR` | Override the cache location (default `~/.cache/chromiumfish/<version>/`). |
| `CHROMIUMFISH_GEOIP_VERSION` | Pin the ip2tz DB version (e.g. `2026.06`) or `"latest"`. |
| `CHROMIUMFISH_GEOIP_TTL` | How often to re-check the "latest" ip2tz pointer. |

## CLI

```bash
chromiumfish fetch [--browser-version X] [--force]   # download + cache
chromiumfish path                                     # print binary path
chromiumfish clear                                    # wipe the cache
chromiumfish --version
```
