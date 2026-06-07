# chromiumfish (Node)

Stealth Chromium with a drop-in [Playwright](https://playwright.dev) harness.

```bash
npm install chromiumfish playwright-core
npx chromiumfish fetch        # download + cache the browser build
```

## Usage

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: 27182, headless: true });
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
| `personaSeed` | — | Integer seed for a stable, internally-consistent fingerprint persona. |
| `headless` | `true` | Run headless (SwiftShader). |
| `proxy` | — | Playwright proxy object, e.g. `{ server, username, password }`. |
| `windowSize` | `[1920, 1080]` | Window dimensions (`null` to omit). |
| `version` | pinned | Override the browser build version. |
| `download` | `true` | Auto-download the build if missing. |
| `args` | — | Extra Chromium flags. |
| _...rest_ | — | Forwarded to `chromium.launch()`. |

## CLI

```bash
npx chromiumfish fetch [--browser-version X] [--force]   # download + cache
npx chromiumfish path                                     # print binary path
npx chromiumfish clear                                    # wipe the cache
npx chromiumfish --version
```

Builds are cached under `~/.cache/chromiumfish/<version>/` (override with
`CHROMIUMFISH_CACHE_DIR`). Pin a build with `CHROMIUMFISH_VERSION`.

## License

MIT © Arman Hossain. See the [repository](https://github.com/arman-bd/chromiumfish).
