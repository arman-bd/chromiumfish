---
title: JavaScript API
parent: API Reference
nav_order: 2
---

# JavaScript API
{: .no_toc }

1. TOC
{:toc}

---

```bash
npm install chromiumfish playwright-core
```

`playwright-core` is a peer dependency. You don't need to run `playwright install` — ChromiumFish fetches and launches its own browser build.

## `ChromiumFish(options)`

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: "alpha-7", headless: true });
const page = await browser.newPage();
await page.goto("https://example.com");
await browser.close();
```

Returns a standard Playwright
[`Browser`](https://playwright.dev/docs/api/class-browser). The caller owns its
lifecycle, so call `browser.close()` when done.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `personaSeed` | `string` | — | String id for a stable, internally consistent fingerprint persona. Any stable string works (a numeric string is used as-is, any other string is hashed to a persona). Omit for the build's default persona. |
| `headless` | `boolean` | `true` | Run headless (SwiftShader). |
| `proxy` | `object` | — | Playwright proxy object: `{ server, username, password }`. |
| `windowSize` | `[number, number] \| null` | `[1920, 1080]` | Window dimensions. Pass `null` to omit the flag. |
| `version` | `string` | `150.0.7844` | Override the pinned browser build version. |
| `download` | `boolean` | `true` | Download the build automatically if it isn't cached. |
| `timezone` | `string` | — | `"auto"` resolves the egress IP's IANA timezone via the ip2tz DB and sets the browser TZ. An IANA string like `"Europe/Berlin"` is used verbatim. Omit to disable timezone handling. |
| `args` | `string[]` | — | Extra Chromium command-line flags. |
| `...rest` | `LaunchOptions` | — | Any other Playwright `LaunchOptions` are forwarded to `chromium.launch()`. |

{: .tip }
> Set `timezone: "auto"` when you run behind a proxy so the browser's timezone matches the exit IP instead of the host machine.

## AI agent

The native in-browser agent (perceive → think → act). See the [AI Agent guide](../ai-agent)
for the full picture; this is the API surface. Needs a WebSocket — Node 22+ has a global one;
on Node &lt;22 add the optional `ws` package (`npm install ws`).

### `launchAgent` / `withAgent`

```ts
import { withAgent } from "chromiumfish";

// withAgent shuts the browser down for you (like Python's `with launch_agent()`)
const whose = await withAgent({ typing: "human" }, (agent) =>
  agent.runTask(
    "Open http://127.0.0.1:8000/login, sign in with demo@bytetunnels.test / " +
    "password123, and tell me whose account you land on."
  ).then((r) => r.finalText));
```

`launchAgent(opts)` returns `{ agent, close }` if you want to manage the lifecycle yourself.
LLM config is read from `OPENAI_API_BASE` / `OPENAI_API_KEY` / `OPENAI_API_MODEL` (a nearby
`.env` is auto-loaded).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `port` | `number` | `9222` | DevTools remote-debugging port. |
| `chrome` | `string` | `CHROME_BIN` / cached build | Path to the ChromiumFish binary. |
| `model` | `string` | `OPENAI_API_MODEL` | Model for this session. |
| `typing` | `string \| [kd, ku, mult]` | `"human"` | `"human"` (~75 WPM), `"fast"`, `"instant"`, or a `[keyDown, keyUp, longMultiplier]` triple (numbers = ms). |
| `loadDotenv` | `boolean` | `true` | Auto-load a nearby `.env`. |
| `extraArgs` | `string[]` | — | Extra Chromium flags (e.g. pass `--agent-llm-url=…` directly). |

### `AgentClient.runTask`

```ts
const r = await agent.runTask(goal, { url, maxSteps, model, plan });
```

`url` navigates there first; `maxSteps` (default 25) caps the loop; `plan` replays a resolved
plan. Returns an **`AgentResult`** with `success`, `finalText`, `steps` (each tagged
`recorded` / `replayed` / `healed`), and `summary()`. Pass a prior run's `steps` back as
`{ plan }` to replay it deterministically (the LLM only heals drift).

## Timezone helpers

The same ip2tz lookup used by `timezone: "auto"` is exposed directly. Both helpers return an IANA timezone string (or `null` if the IP can't be resolved). The DB downloads once and caches.

```javascript
import { lookupTimezone, resolveTimezone } from "chromiumfish";

const tz = await lookupTimezone("8.8.8.8");
console.log(tz); // "America/Los_Angeles"

const own = await resolveTimezone(); // your own egress IP's timezone
console.log(own);
```

`lookupTimezone(ip)` looks up any IP. `resolveTimezone()` resolves the timezone of your own egress IP.

## Module functions

| Function | Description |
|----------|-------------|
| `fetchBrowser(version?, force?) => Promise<string>` | Download and cache the build; resolves to the binary path. |
| `binaryPath(version?, download?) => Promise<string>` | Path to the cached binary, fetching if needed (and allowed). |
| `installDir(version?) => string` | The per-version install directory. |

## Environment variables

| Variable | Description |
|----------|-------------|
| `CHROMIUMFISH_VERSION` | Pin the browser build version. |
| `CHROMIUMFISH_CACHE_DIR` | Override the cache location (default `~/.cache/chromiumfish/<version>/`). |
| `CHROMIUMFISH_GEOIP_VERSION` | Pin the ip2tz DB version (e.g. `2026.06`) or `latest`. |
| `CHROMIUMFISH_GEOIP_TTL` | How often to re-check the `latest` ip2tz pointer. |

{: .note }
> The ip2tz DB tracks the monthly `latest` build and re-checks weekly. Set `CHROMIUMFISH_GEOIP_VERSION=2026.06` to pin a fixed DB for reproducible timezone resolution.

## CLI

```bash
npx chromiumfish fetch [--browser-version X] [--force]   # download + cache
npx chromiumfish path                                     # print binary path
npx chromiumfish clear                                    # wipe the cache
npx chromiumfish --version
```
