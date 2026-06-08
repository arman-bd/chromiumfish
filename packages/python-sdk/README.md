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

with Chromiumfish(persona_seed="alpha-7", headless=True) as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
    page.screenshot(path="fp.png")
```

**Async**

```python
import asyncio
from chromiumfish.async_api import AsyncChromiumfish

async def main():
    async with AsyncChromiumfish(persona_seed="alpha-7") as browser:
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
| `persona_seed` | `None` | String id for a stable, internally-consistent fingerprint persona (any string; a number works too). |
| `headless` | `True` | Run headless (SwiftShader). |
| `proxy` | `None` | Playwright proxy dict, e.g. `{"server": "http://host:port", "username": ..., "password": ...}`. |
| `window_size` | `(1920, 1080)` | Window dimensions. |
| `version` | pinned | Override the browser build version. |
| `download` | `True` | Auto-download the build if missing. |
| `timezone` | `None` | `"auto"` resolves the egress IP's IANA timezone via the downloadable `ip2tz` DB and sets the browser's `TZ`; an IANA string (e.g. `"Europe/Berlin"`) is used verbatim. |
| `args` | `None` | Extra Chromium flags. |
| `**launch_kwargs` | — | Forwarded to `chromium.launch()`. |

### IP-to-Timezone

`timezone="auto"` aligns the browser clock with the egress IP (handy behind a
proxy). It uses a compact `ip2tz` database downloaded once and cached; you can
also query it directly:

```python
from chromiumfish import lookup_timezone, resolve_timezone

lookup_timezone("8.8.8.8")                 # -> "America/Los_Angeles"
resolve_timezone(proxy="http://user:pass@host:port")   # egress IP -> timezone
```

The DB auto-updates: it tracks the `latest` monthly build (cached, re-checked
weekly), so you get fresh data without upgrading the SDK. Pin a fixed version
with `CHROMIUMFISH_GEOIP_VERSION=2026.06` for reproducibility.

## CLI

```bash
chromiumfish fetch [--browser-version X] [--force]   # download + cache
chromiumfish path                                     # print binary path
chromiumfish clear                                    # wipe the cache
chromiumfish --version
```

Builds are cached under `~/.cache/chromiumfish/<version>/` (override with
`CHROMIUMFISH_CACHE_DIR`). Pin a build with `CHROMIUMFISH_VERSION`.

## Attribution

IP Geolocation by <a href='https://db-ip.com'>DB-IP</a> — the `ip2tz` timezone
database is derived from [DB-IP City Lite][dbip], used under [CC BY 4.0][ccby].

[dbip]: https://db-ip.com/db/download/ip-to-city-lite
[ccby]: https://creativecommons.org/licenses/by/4.0/

## License

MIT © Arman Hossain. See the [repository](https://github.com/arman-bd/chromiumfish).
