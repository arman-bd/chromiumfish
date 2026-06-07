---
title: Quickstart
nav_order: 3
---

# Quickstart
{: .no_toc }

1. TOC
{:toc}

---

## Launch a stealth browser

### Python (sync)

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed=27182, headless=True) as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
    page.screenshot(path="fingerprint.png")
```

### Python (async)

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

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: 27182, headless: true });
const page = await browser.newPage();
await page.goto("https://abrahamjuliot.github.io/creepjs/");
await page.screenshot({ path: "fingerprint.png" });
await browser.close();
```

The object you get back is a **standard Playwright `Browser`**. Use contexts, pages,
routing, tracing, and selectors exactly as you would with vanilla Playwright.

## Using a proxy

### Python

```python
with Chromiumfish(
    persona_seed=27182,
    proxy={
        "server": "http://proxy.example.com:8000",
        "username": "user",
        "password": "pass",
    },
) as browser:
    ...
```

### Node

```javascript
const browser = await ChromiumFish({
  personaSeed: 27182,
  proxy: { server: "http://proxy.example.com:8000", username: "user", password: "pass" },
});
```

{: .tip }
> Pair a residential proxy with a matching persona for best results — a clean IP plus a
> coherent fingerprint clears most bot walls. Keep the proxy's geo consistent with the
> persona's locale.

## Contexts and pages

```python
with Chromiumfish(persona_seed=27182) as browser:
    context = browser.new_context(locale="en-US")
    page = context.new_page()
    page.goto("https://example.com")
```

## First-run download

On the first launch (or `chromiumfish fetch`), the build is downloaded and cached.
Subsequent runs reuse the cache, so startup is instant.
