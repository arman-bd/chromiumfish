# chromiumfish (Node)

Stealth Chromium with a drop-in [Playwright](https://playwright.dev) harness.

```bash
npm install chromiumfish playwright-core
npx chromiumfish fetch        # download + cache the browser build
```

## Usage

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: "alpha-7", headless: true });
const page = await browser.newPage();
await page.goto("https://abrahamjuliot.github.io/creepjs/");
await page.screenshot({ path: "fp.png" });
await browser.close();
```

`ChromiumFish()` returns a standard Playwright `Browser`, so `newContext`,
`newPage`, routing, tracing, etc. all work as usual.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `personaSeed` | — | String id for a stable, internally-consistent fingerprint persona (any string; a number works too). |
| `headless` | `true` | Run headless (SwiftShader). |
| `proxy` | — | Playwright proxy object, e.g. `{ server, username, password }`. |
| `windowSize` | `[1920, 1080]` | Window dimensions (`null` to omit). |
| `version` | pinned | Override the browser build version. |
| `download` | `true` | Auto-download the build if missing. |
| `timezone` | — | `"auto"` resolves the egress IP's IANA timezone via the downloadable `ip2tz` DB and sets the browser's `TZ`; an IANA string (e.g. `"Europe/Berlin"`) is used verbatim. |
| `args` | — | Extra Chromium flags. |
| _...rest_ | — | Forwarded to `chromium.launch()`. |

### IP-to-Timezone

`timezone: "auto"` aligns the browser clock with the egress IP (handy behind a
proxy). It uses a compact `ip2tz` database downloaded once and cached; you can
also query it directly:

```ts
import { lookupTimezone, resolveTimezone } from "chromiumfish";

await lookupTimezone("8.8.8.8");   // -> "America/Los_Angeles"
await resolveTimezone();           // own egress IP -> timezone
```

The DB auto-updates: it tracks the `latest` monthly build (cached, re-checked
weekly), so you get fresh data without upgrading the SDK. Pin a fixed version
with `CHROMIUMFISH_GEOIP_VERSION=2026.06` for reproducibility.

## CLI

```bash
npx chromiumfish fetch [--browser-version X] [--force]   # download + cache
npx chromiumfish path                                     # print binary path
npx chromiumfish clear                                    # wipe the cache
npx chromiumfish --version
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
