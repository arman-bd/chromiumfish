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
lifecycle — call `browser.close()` when done.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `personaSeed` | `number` | — | Integer seed for a stable, internally consistent fingerprint persona. |
| `headless` | `boolean` | `true` | Run headless (SwiftShader). |
| `proxy` | `object` | — | Playwright proxy object: `{ server, username, password }`. |
| `windowSize` | `[number, number] \| null` | `[1920, 1080]` | Window dimensions. Pass `null` to omit the flag. |
| `version` | `string` | — | Override the browser build version. |
| `download` | `boolean` | `true` | Download the build automatically if it isn't cached. |
| `args` | `string[]` | — | Extra Chromium command-line flags. |
| `...rest` | `LaunchOptions` | — | Any other Playwright `LaunchOptions` are forwarded to `chromium.launch()`. |

## Module functions

| Function | Description |
|----------|-------------|
| `fetchBrowser(version?, force?) => Promise<string>` | Download + cache the build; resolves to the binary path. |
| `binaryPath(version?, download?) => Promise<string>` | Path to the cached binary, fetching if needed (and allowed). |
| `installDir(version?) => string` | The per-version install directory. |

## CLI

```bash
npx chromiumfish fetch [--browser-version X] [--force]   # download + cache
npx chromiumfish path                                     # print binary path
npx chromiumfish clear                                    # wipe the cache
npx chromiumfish --version
```
