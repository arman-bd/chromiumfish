---
title: External Agents
nav_order: 5
---

# External Agents
{: .no_toc }

Drive ChromiumFish from third-party autonomous-agent frameworks — [Hermes Agent](https://github.com/NousResearch/hermes-agent), [OpenClaw](https://docs.openclaw.ai), [browser-use](https://github.com/browser-use/browser-use), and anything else that speaks the Chrome DevTools Protocol or Playwright.
{: .fs-6 .fw-300 }

1. TOC
{:toc}

---

## The short version

ChromiumFish **is** Chromium, so it speaks the same Chrome DevTools Protocol (CDP) every browser-agent framework already drives. You don't need a special build, a plugin, or a patched client — you need to point the agent at a running instance. There are two ways in:

1. **Attach over CDP** — launch ChromiumFish with a remote-debugging endpoint and give the agent its URL. **Recommended**, because the persona/proxy/timezone you launch with are already active, so the agent inherits the full stealth persona without knowing anything about it.
2. **Launch by binary path** — hand the agent the path to the ChromiumFish binary and let it start the browser itself (Playwright/Puppeteer `executablePath` style).

`chromiumfish serve` is the one command that covers route 1.

## `chromiumfish serve`

Launches a plain CDP endpoint for an external agent to attach to. Unlike [`launch_agent`](ai-agent) (which wires up the *native* in-browser agent), `serve` adds **no** `--agent-*` switches — it just exposes DevTools with the persona you choose.

```console
$ chromiumfish serve --persona-seed alice --window-size 1920x1080
ChromiumFish Chrome/149.0.7827.115 ready — CDP endpoint for external agents
  HTTP : http://127.0.0.1:9222   (discovery: http://127.0.0.1:9222/json/version)
  WS   : ws://127.0.0.1:9222/devtools/browser/2efe109e-...

Attach an agent, e.g.:
  Hermes       ~/.hermes/config.yaml  ->  browser: { cdp_url: "http://127.0.0.1:9222" }
  browser-use  BrowserSession(cdp_url="http://127.0.0.1:9222")
  OpenClaw     profile  cdpUrl: "http://127.0.0.1:9222"
Ctrl-C to stop.
```

It blocks until you press <kbd>Ctrl-C</kbd> (or it receives `SIGTERM`), then shuts the browser down and removes its temporary profile.

| Flag | Default | Notes |
|---|---|---|
| `--port` | `9222` | Remote-debugging port (bound to `127.0.0.1`). |
| `--persona-seed` | _none_ | Stable fingerprint persona — see [Personas](personas). |
| `--proxy` | _none_ | `scheme://[user:pass@]host:port`. |
| `--window-size` | `1920x1080` | `WIDTHxHEIGHT`. |
| `--timezone` | _none_ | An IANA zone, or `auto` to derive it from the egress IP. |
| `--headless` | off (headed) | Run headless. |
| `--browser-version` | pinned build | Override the build version. |
| `--extra-args` | _none_ | Comma-separated extra Chromium flags. |
| `--timeout` | `30` | Seconds to wait for the endpoint to come up. |

> Node usage is identical: `npx chromiumfish serve --persona-seed alice`.

Prefer attaching to a `serve` endpoint over having the agent launch the binary: it's the mode where your persona, proxy, and timezone are guaranteed to be active.

## Use it as an MCP server

For MCP clients (Claude Code, Claude Desktop, Cursor, Windsurf, …), ChromiumFish ships a first-party **MCP server** that exposes the stealth browser as tools — no glue code. It's in **both** SDKs:

- **Node**: `chromiumfish mcp` (or zero-install `npx chromiumfish mcp`)
- **Python** (≥3.10): `pip install "chromiumfish[mcp]"`, then `chromiumfish mcp`

```bash
chromiumfish mcp --persona-seed alice        # speaks MCP over stdio
```

Tools: `navigate`, `snapshot` (visible interactive elements as `[i] <role> "label" <css-selector>`), `get_text`, `screenshot`, `click(selector)`, `type_text(selector, text, submit)`, `eval_js(expression)`, and `run_task(goal)`. The granular tools need **no server-side LLM** — your MCP client is the brain; `run_task` delegates a whole plain-language goal to the fork's native in-browser agent and needs an OpenAI-compatible LLM (`OPENAI_API_*` or `--llm-*`). The browser launches on first use with the persona/proxy/timezone you pass, and is torn down when the client disconnects.

Wire it into a client — e.g. Claude Desktop (`claude_desktop_config.json`) or Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "chromiumfish": {
      "command": "chromiumfish",
      "args": ["mcp", "--persona-seed", "alice"]
    }
  }
}
```

Zero-install runners work too — `npx` (Node) or `uvx` (Python):

```json
{ "mcpServers": { "chromiumfish": { "command": "npx", "args": ["-y", "chromiumfish", "mcp"] } } }
```

```json
{ "mcpServers": { "chromiumfish": { "command": "uvx", "args": ["--from", "chromiumfish[mcp]", "chromiumfish", "mcp"] } } }
```

Flags mirror `serve` (`--persona-seed`, `--proxy`, `--window-size`, `--port`, `--typing`) plus `--headed` to show the window and `--llm-key/--llm-base/--llm-model` for `run_task`.

## Hermes Agent

[Hermes](https://github.com/NousResearch/hermes-agent) (Nous Research, MIT) connects to a local Chromium-family browser over raw CDP. Point it at a `serve` endpoint:

**1. Start the browser:**

```bash
chromiumfish serve --persona-seed alice
```

**2. Tell Hermes to attach** — in `~/.hermes/config.yaml`:

```yaml
model:
  default: "your/model"        # any OpenRouter / OpenAI-compatible model
  provider: "openrouter"       # key in ~/.hermes/.env

browser:
  cdp_url: "http://127.0.0.1:9222"   # Hermes fetches /json/version to find the ws
```

(Equivalently: `export BROWSER_CDP_URL=http://127.0.0.1:9222`, or run `/browser connect` inside the Hermes REPL.)

**3. Run a task:**

```bash
hermes chat -q "Open https://example.com and tell me the main heading." --toolsets browser
```

Hermes drives ChromiumFish through its full tool set — `browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`, `browser_scroll`, `browser_vision`. This path is verified end-to-end against the published build.

> **Tip:** Hermes' `browser_snapshot` *compact* view prioritizes interactive controls and can omit text sitting in bare `<div>`/`<span>` nodes. If you need an exact value buried in non-interactive text, prompt Hermes to use `browser_vision` (a screenshot) or read the specific field — the data is fully present over CDP, it's just trimmed from the compact summary.

## browser-use

[browser-use](https://github.com/browser-use/browser-use) drives the browser over raw CDP. Either attach to a `serve` endpoint:

```python
from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession

session = BrowserSession(browser_profile=BrowserProfile(cdp_url="http://127.0.0.1:9222"))
agent = Agent(task="...", browser_session=session)
```

…or let browser-use launch the binary itself (persona via `args`):

```python
import subprocess
from browser_use.browser import BrowserProfile, BrowserSession

exe = subprocess.check_output(["chromiumfish", "path"], text=True).strip()
session = BrowserSession(browser_profile=BrowserProfile(
    executable_path=exe,
    args=["--persona-seed=alice", "--window-size=1920,1080"],
))
```

## OpenClaw

[OpenClaw](https://docs.openclaw.ai) supports both routes. In `~/.openclaw/openclaw.json`, either point a **local-managed** profile at the binary:

```jsonc
{
  "browser": {
    "profiles": {
      "chromiumfish": {
        "executablePath": "<output of `chromiumfish path`>",
        "extraArgs": ["--persona-seed=alice", "--window-size=1920,1080"]
      }
    }
  }
}
```

…or attach a **remote** profile to a `serve` endpoint:

```jsonc
{ "browser": { "profiles": { "chromiumfish": { "cdpUrl": "http://127.0.0.1:9222" } } } }
```

## Anything else

Any client that drives Chromium works, because nothing here is ChromiumFish-specific:

- **Raw CDP** (Python `websocket-client`, Node `ws`, `cdp-use`, …) — connect to the `ws://` endpoint from `/json/version`.
- **Playwright** — `chromium.connect_over_cdp("http://127.0.0.1:9222")` (Python) / `chromium.connectOverCDP(...)` (Node).
- **Puppeteer** — `puppeteer.connect({ browserURL: "http://127.0.0.1:9222" })`.

## How it works

ChromiumFish exposes a standard DevTools endpoint, so the full perception + action surface an agent needs is available over CDP — `Page.navigate`, `Input.dispatchMouseEvent`/`dispatchKeyEvent`, `Page.captureScreenshot`, and the renderer-served `Runtime`, `DOM`, `DOMSnapshot`, and `Accessibility` domains agents use to read a page. Crucially, the spoofing lives in the engine, not in a script: `navigator.webdriver` stays `false` even under CDP and there are no `cdc_` automation artifacts, so attaching an agent doesn't blow the persona's cover. That's the whole point of attaching to a `serve` endpoint you launched with `--persona-seed` — the agent operates a browser that already looks like a real, consistent person.
