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

const browser = await ChromiumFish({ personaSeed: 27182, headless: true });
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
| `personaSeed` | `number` | — | Integer seed for a stable, internally consistent fingerprint persona. Omit for the build's default persona. |
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
