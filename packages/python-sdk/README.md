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
    page.goto("https://example.com")
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

### Geolocation (GPS)

Pin a static GPS position with two flags through `args`. ChromiumFish auto-grants the
Geolocation permission (no prompt) and reports those exact coordinates to every frame,
never querying the real location providers:

```python
with Chromiumfish(
    persona_seed="alpha-7",
    args=["--persona-lat=48.8584", "--persona-lng=2.2945"],  # optional: --persona-accuracy=<m> (default 40)
) as browser:
    ...
```

Keep the location aligned with the exit IP and timezone. More:
[chromiumfish.com/personas#geolocation-gps](https://chromiumfish.com/personas#geolocation-gps).

### Mobile / OS persona

By default the persona is Windows desktop Chrome. `--persona-os` (through `args`) switches
the whole OS family — `win` (default), `mac`, or `android`, a seed-driven Pixel-family phone
(mobile UA/hints, touch, phone screen, Mali WebGL):

```python
with Chromiumfish(persona_seed="alpha-7", args=["--persona-os=android"]) as browser:
    ...  # navigator.userAgentData.mobile === True
```

The Android persona is coherent but not airtight — fonts, exact-match canvas, and
locale/timezone still carry desktop tells, so pair it with a mobile-region proxy + timezone
and don't rely on it against the strictest detectors. More:
[chromiumfish.com/personas#mobile-and-os-persona](https://chromiumfish.com/personas#mobile-and-os-persona).

## AI agent

ChromiumFish ships a native in-browser agent (perceive → think → act, driven by an
OpenAI-compatible LLM). `launch_agent` starts the browser with the agent layer and connects
over CDP; `run_task` drives it from a plain-language goal.

```python
from chromiumfish import launch_agent

# LLM config: a nearby .env (OPENAI_API_*), or pass api_key=/api_base=/model= to launch_agent
with launch_agent(typing="human") as agent:   # typing: "human" (default) / "fast" / "instant"
    r = agent.run_task("Search DuckDuckGo for 'chromiumfish' and give me the first result's URL.")
    print(r.final_text)
```

`run_task` returns an `AgentResult` (`success`, `final_text`, `steps`, `summary()`); pass a
prior run's `steps` back as `plan=` to replay a flow deterministically. Install the agent
extra (`pip install "chromiumfish[agent]"`) for the `websocket-client` dependency. Point at a
local build with `CHROME_BIN=…/ChromiumFish`. Full guide:
[chromiumfish.com/ai-agent](https://chromiumfish.com/ai-agent).

## External agents

Prefer a third-party framework (Hermes, OpenClaw, browser-use, Playwright, …)? `chromiumfish
serve` exposes a plain CDP endpoint — with your persona/proxy/timezone active — for any of them
to attach to:

```bash
chromiumfish serve --persona-seed alice            # -> http://127.0.0.1:9222
# e.g. Hermes ~/.hermes/config.yaml: browser: { cdp_url: "http://127.0.0.1:9222" }
```

Or run it as an **MCP server** for Claude Code/Desktop, Cursor, etc. — `pip install
"chromiumfish[mcp]"` (Python ≥3.10), then:

```bash
chromiumfish mcp --persona-seed alice              # exposes browser tools over MCP (stdio)
```

Full guide: [chromiumfish.com/agents](https://chromiumfish.com/agents).

## CLI

```bash
chromiumfish fetch [--browser-version X] [--force]   # download + cache
chromiumfish path                                     # print binary path
chromiumfish serve [--port 9222] [--persona-seed S]  # CDP endpoint for external agents
                   [--proxy URL] [--window-size WxH] [--timezone Z] [--headless]
                   [--browser-version X] [--extra-args ARGS] [--timeout S]
chromiumfish mcp   [--persona-seed S] [--headed]      # MCP server (Claude, Cursor, ...)
                   [--proxy URL] [--window-size WxH] [--typing T] [--llm-key K]
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
