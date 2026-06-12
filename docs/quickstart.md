---
title: Quickstart
nav_order: 3
---

# Quickstart
{: .no_toc }

1. TOC
{:toc}

---

## Launch a browser

### Python (sync)

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="alpha-7", headless=True) as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
    page.screenshot(path="fingerprint.png")
```

### Python (async)

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

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: "alpha-7", headless: true });
const page = await browser.newPage();
await page.goto("https://abrahamjuliot.github.io/creepjs/");
await page.screenshot({ path: "fingerprint.png" });
await browser.close();
```

The object you get back is a **standard Playwright `Browser`**. Use contexts, pages,
routing, tracing, and selectors exactly as you would with vanilla Playwright.

## Watch it run while you build

Launches are headless by default. While you're writing a selector or stepping through a
login, open a visible window with `headless=False` and drop into the Playwright Inspector
with `page.pause()`.

### Python

```python
with Chromiumfish(persona_seed="alpha-7", headless=False) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
    page.pause()   # opens the Inspector; step through and pick selectors
```

### Node

```javascript
const browser = await ChromiumFish({ personaSeed: "alpha-7", headless: false });
const page = await browser.newPage();
await page.goto("https://example.com");
await page.pause();
```

{: .note }
> Headful mode needs a display. On a headless server, run under `xvfb-run`, or just keep
> `headless=True` and use `page.screenshot(...)` to see what the page looked like.

## Using a proxy

### Python

```python
with Chromiumfish(
    persona_seed="alpha-7",
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
  personaSeed: "alpha-7",
  proxy: { server: "http://proxy.example.com:8000", username: "user", password: "pass" },
});
```

{: .tip }
> Pair a residential proxy with a matching persona for best results. A clean IP plus a
> coherent fingerprint clears most bot walls. Keep the proxy's geo consistent with the
> persona's locale.

## Match the timezone to your proxy

A browser whose clock sits in a different timezone than its IP address is an easy
tell. Set `timezone="auto"` and the SDK resolves the egress IP to an IANA timezone
(using the downloadable ip2tz DB) and sets the browser's timezone to match.

### Python

```python
with Chromiumfish(
    persona_seed="alpha-7",
    proxy={"server": "http://proxy.example.com:8000"},
    timezone="auto",
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

### Node

```javascript
const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  proxy: { server: "http://proxy.example.com:8000" },
  timezone: "auto",
});
```

If you already know the location, pass an IANA name directly, for example
`timezone="Europe/Berlin"` (Python) or `timezone: "Europe/Berlin"` (Node). Leaving
it out disables timezone handling entirely.

## Scrape a page

A small but realistic flow: open a page, wait for the network to settle, pull a bit
of text and an attribute, then save a screenshot.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="alpha-7") as browser:
    page = browser.new_page()
    page.goto("https://news.ycombinator.com", wait_until="domcontentloaded")

    title = page.inner_text(".titleline a")
    link = page.get_attribute(".titleline a", "href")
    print(title, link)

    page.screenshot(path="hn.png", full_page=True)
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: "alpha-7" });
const page = await browser.newPage();
await page.goto("https://news.ycombinator.com", { waitUntil: "domcontentloaded" });

const title = await page.innerText(".titleline a");
const link = await page.getAttribute(".titleline a", "href");
console.log(title, link);

await page.screenshot({ path: "hn.png", fullPage: true });
await browser.close();
```

## Go faster by blocking heavy resources

Most scrapes don't need images, video, or web fonts. Abort those requests with
Playwright routing and pages load noticeably faster on slow proxies.

### Python

```python
with Chromiumfish(persona_seed="alpha-7") as browser:
    page = browser.new_page()
    page.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in ("image", "media", "font")
        else route.continue_(),
    )
    page.goto("https://example.com", wait_until="domcontentloaded")
```

### Node

```javascript
const browser = await ChromiumFish({ personaSeed: "alpha-7" });
const page = await browser.newPage();
await page.route("**/*", (route) => {
  const type = route.request().resourceType();
  return ["image", "media", "font"].includes(type)
    ? route.abort()
    : route.continue();
});
await page.goto("https://example.com", { waitUntil: "domcontentloaded" });
```

{: .note }
> Blocking fonts can change text metrics on some sites. If a page renders oddly or a
> fingerprint check cares about fonts, drop `"font"` from the block list.

## Contexts and pages

```python
with Chromiumfish(persona_seed="alpha-7") as browser:
    context = browser.new_context(locale="en-US")
    page = context.new_page()
    page.goto("https://example.com")
```

## First-run download

On the first launch (or `chromiumfish fetch`), the build is downloaded and cached.
Subsequent runs reuse the cache, so startup is fast.
