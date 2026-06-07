# chromiumfish (Python)

Stealth Chromium with a drop-in [Playwright](https://playwright.dev) harness.

```bash
pip install chromiumfish
chromiumfish fetch        # download + cache the browser build
```

## Usage

**Sync**

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed=27182, headless=True) as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
    page.screenshot(path="fp.png")
```

**Async**

```python
import asyncio
from chromiumfish.async_api import AsyncChromiumfish

async def main():
    async with AsyncChromiumfish(persona_seed=27182) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")
        print(await page.title())

asyncio.run(main())
```

The returned object is a standard Playwright `Browser`, so `new_context`,
`new_page`, routing, tracing, etc. all work as usual.

## Options

| Argument | Default | Description |
|----------|---------|-------------|
| `persona_seed` | `None` | Integer seed for a stable, internally-consistent fingerprint persona. |
| `headless` | `True` | Run headless (SwiftShader). |
| `proxy` | `None` | Playwright proxy dict, e.g. `{"server": "http://host:port", "username": ..., "password": ...}`. |
| `window_size` | `(1920, 1080)` | Window dimensions. |
| `version` | pinned | Override the browser build version. |
| `download` | `True` | Auto-download the build if missing. |
| `args` | `None` | Extra Chromium flags. |
| `**launch_kwargs` | — | Forwarded to `chromium.launch()`. |

## CLI

```bash
chromiumfish fetch [--browser-version X] [--force]   # download + cache
chromiumfish path                                     # print binary path
chromiumfish clear                                    # wipe the cache
chromiumfish --version
```

Builds are cached under `~/.cache/chromiumfish/<version>/` (override with
`CHROMIUMFISH_CACHE_DIR`). Pin a build with `CHROMIUMFISH_VERSION`.

## License

MIT © Arman Hossain. See the [repository](https://github.com/arman-bd/chromiumfish).
