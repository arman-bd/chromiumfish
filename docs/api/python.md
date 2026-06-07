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
| `persona_seed` | `int` | — | Integer seed for a stable, internally consistent fingerprint persona. Omit for the build's default persona. |
| `headless` | `bool` | `True` | Run headless (SwiftShader). |
| `proxy` | `dict` | — | Playwright proxy dict: `{"server": ..., "username": ..., "password": ...}`. |
| `window_size` | `tuple` | `(1920, 1080)` | Window dimensions. Pass `None` to omit the flag. |
| `version` | `str` | — | Override the browser build version (defaults to the pinned build). |
| `download` | `bool` | `True` | Download the build automatically if it isn't cached. |
| `args` | `list[str]` | — | Extra Chromium command-line flags. |
| `**launch_kwargs` | `Any` | — | Any other keyword arguments are forwarded to `chromium.launch()`. |

## Module functions

| Function | Description |
|----------|-------------|
| `fetch(version=None, *, force=False) -> Path` | Download + cache the build; returns the binary path. |
| `binary_path(version=None, *, download=True) -> Path` | Path to the cached binary, fetching if needed (and allowed). |
| `install_dir(version=None) -> Path` | The per-version install directory. |

## CLI

```bash
chromiumfish fetch [--browser-version X] [--force]   # download + cache
chromiumfish path                                     # print binary path
chromiumfish clear                                    # wipe the cache
chromiumfish --version
```
