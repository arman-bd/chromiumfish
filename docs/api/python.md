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

with Chromiumfish(persona_seed="alpha-7", headless=True) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

A context manager that launches the browser and yields a Playwright
[`Browser`](https://playwright.dev/python/docs/api/class-browser). Closing the context
closes the browser and stops Playwright.

## `AsyncChromiumfish` (async)

```python
from chromiumfish.async_api import AsyncChromiumfish

async with AsyncChromiumfish(persona_seed="alpha-7") as browser:
    page = await browser.new_page()
```

Same API, returns an async `Browser`.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `persona_seed` | `str` | none | String id for a stable, internally consistent fingerprint persona. Any stable string works (a numeric string is used as-is, any other string is hashed to a persona). Omit for the build's default persona. |
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
    persona_seed="alpha-7",
    proxy={"server": "http://proxy.example:8080"},
    timezone="auto",
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

## AI agent

The native in-browser agent (perceive → think → act). See the [AI Agent guide](../ai-agent)
for the full picture; this is the API surface. Needs `websocket-client`:

```bash
pip install "chromiumfish[agent]"
```

### `launch_agent` (context manager)

```python
from chromiumfish import launch_agent

with launch_agent(typing="human") as agent:           # launches the build + agent layer
    r = agent.run_task("Open http://127.0.0.1:8000/login, sign in with "
                       "demo@bytetunnels.test / password123, and tell me whose account you land on.")
    print(r.success, r.final_text)
```

The browser is shut down and its temp profile removed on exit. LLM config is read from
`OPENAI_API_BASE` / `OPENAI_API_KEY` / `OPENAI_API_MODEL` (a nearby `.env` is auto-loaded).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `port` | `int` | `9222` | DevTools remote-debugging port. |
| `chrome` | `str` | `CHROME_BIN` / cached build | Path to the ChromiumFish binary. |
| `model` | `str` | `OPENAI_API_MODEL` | Model for this session. |
| `typing` | `str \| tuple` | `"human"` | `"human"` (~75 WPM), `"fast"`, `"instant"`, or a `(key_down, key_up, long_multiplier)` triple (numbers = ms). |
| `load_dotenv` | `bool` | `True` | Auto-load a nearby `.env`. |
| `extra_args` | `list[str]` | none | Extra Chromium flags (e.g. pass `--agent-llm-url=…` directly). |

### `AgentClient.run_task`

```python
r = agent.run_task(goal, *, url=None, max_steps=25, model="", plan=None)
```

`url` navigates there first (the agent can also navigate itself); `max_steps` caps the loop;
`plan` replays a previously resolved plan. Returns an **`AgentResult`**:

| Attribute | Description |
|-----------|-------------|
| `success` | Goal reported met. |
| `final_text` | The agent's answer. |
| `steps` | Resolved plan; each step tagged `recorded` / `replayed` / `healed`. |
| `summary()` | One-line digest. |

```python
# Record once, then replay deterministically (LLM only heals drift):
first = agent.run_task("search for 'automation' and open the first result",
                       url="http://127.0.0.1:8000/search")
again = agent.run_task("search for 'automation' and open the first result",
                       url="http://127.0.0.1:8000/search", plan=first.steps)
print(again.summary())   # ok | N steps (N replayed, 0 healed, 0 recorded)
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
