---
title: Recipes
nav_order: 6
---

# Recipes
{: .no_toc }

1. TOC
{:toc}

---

Short, copy-pasteable patterns for common scraping setups. Every example runs against
the SDK as documented in the [Python API](api/python) and [JavaScript API](api/javascript)
references. The object you get back is always a standard Playwright `Browser`, so anything
you already do with Playwright works here too.

## Stable identity per account

Use the account's own id as its `persona_seed`. Any stable string works, so the same
account always rebuilds the same persona and the site sees a returning user instead of a
brand-new device each visit.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

def scrape_account(account_id: str):
    with Chromiumfish(persona_seed=account_id) as browser:
        page = browser.new_page()
        page.goto("https://example.com/account")
        return page.title()
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

async function scrapeAccount(accountId) {
  const browser = await ChromiumFish({ personaSeed: accountId });
  try {
    const page = await browser.newPage();
    await page.goto("https://example.com/account");
    return await page.title();
  } finally {
    await browser.close();
  }
}
```

## Clean one-off scrape

For a single unlinkable session, generate a fresh random id each run. Different ids
produce uncorrelated personas, so two runs can't be tied together through the fingerprint.

### Python

```python
import secrets
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed=secrets.token_hex(8)) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
    print(page.title())
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";
import { randomUUID } from "node:crypto";

const browser = await ChromiumFish({ personaSeed: randomUUID() });
const page = await browser.newPage();
await page.goto("https://example.com");
console.log(await page.title());
await browser.close();
```

## Proxy plus matching timezone

Route through a residential proxy and set `timezone="auto"` so the browser clock matches
the proxy's exit IP. The SDK resolves the egress IP's IANA timezone through the
downloadable ip2tz DB and sets the browser TZ to match. A clock that disagrees with the IP
is an easy tell, so keep them aligned.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(
    persona_seed="alpha-7",
    proxy={
        "server": "http://residential.example.com:8000",
        "username": "user",
        "password": "pass",
    },
    timezone="auto",
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  proxy: {
    server: "http://residential.example.com:8000",
    username: "user",
    password: "pass",
  },
  timezone: "auto",
});
const page = await browser.newPage();
await page.goto("https://example.com");
await browser.close();
```

{: .tip }
> If you already know the proxy's region, pass the IANA name directly
> (e.g. `timezone="Europe/Berlin"`) to skip the IP lookup.

## Multiple pages, one browser, isolated contexts

Launch the browser once and open a new context per task. Each context has its own cookies,
storage, and cache, so the pages stay isolated even though they share one persona and one
browser process. This is faster than relaunching for every page.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

urls = [
    "https://example.com/a",
    "https://example.com/b",
    "https://example.com/c",
]

with Chromiumfish(persona_seed="alpha-7") as browser:
    for url in urls:
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        print(url, page.title())
        context.close()
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const urls = [
  "https://example.com/a",
  "https://example.com/b",
  "https://example.com/c",
];

const browser = await ChromiumFish({ personaSeed: "alpha-7" });
for (const url of urls) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(url);
  console.log(url, await page.title());
  await context.close();
}
await browser.close();
```

## Block images and media to scrape faster

If you only need the HTML, drop image, media, and font requests with Playwright routing.
Pages load faster and you use less bandwidth, which matters on metered proxies.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

BLOCK = {"image", "media", "font"}

with Chromiumfish(persona_seed="alpha-7") as browser:
    context = browser.new_context()
    context.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in BLOCK
        else route.continue_(),
    )
    page = context.new_page()
    page.goto("https://example.com")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const BLOCK = new Set(["image", "media", "font"]);

const browser = await ChromiumFish({ personaSeed: "alpha-7" });
const context = await browser.newContext();
await context.route("**/*", (route) =>
  BLOCK.has(route.request().resourceType())
    ? route.abort()
    : route.continue(),
);
const page = await context.newPage();
await page.goto("https://example.com");
await browser.close();
```

{: .note }
> Some sites lazy-load content or gate it behind images. If a page comes back empty, loosen
> the block set or skip this step for that target.

## Look up a timezone for an IP

You don't need a browser to use the ip2tz DB. The public helpers resolve an IP (or your own
egress IP) to an IANA timezone, which is handy for picking a `timezone=` value up front.

### Python

```python
from chromiumfish import lookup_timezone, resolve_timezone

print(lookup_timezone("8.8.8.8"))  # "America/Los_Angeles"
print(resolve_timezone())          # your egress IP's timezone
```

### Node

```javascript
import { lookupTimezone, resolveTimezone } from "chromiumfish";

console.log(await lookupTimezone("8.8.8.8")); // "America/Los_Angeles"
console.log(await resolveTimezone());         // your egress IP's timezone
```

The DB downloads once and caches. It tracks the monthly "latest" build and re-checks weekly.
`lookup_timezone` / `lookupTimezone` returns `None`/`null` when an IP has no mapping.

## Pin versions for reproducible runs

For builds you want to reproduce later, pin the browser version with `version=` and pin the
ip2tz DB with `CHROMIUMFISH_GEOIP_VERSION`. With both pinned, the same code produces the same
browser and the same timezone data on any machine.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="alpha-7", version="150.0.7844") as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: "alpha-7", version: "150.0.7844" });
const page = await browser.newPage();
await page.goto("https://example.com");
await browser.close();
```

Pin the geoip DB through the environment so the timezone data stays fixed too:

```bash
export CHROMIUMFISH_GEOIP_VERSION=2026.06
```

You can also pin the browser version in the environment with `CHROMIUMFISH_VERSION` instead
of passing `version=` on every call.

## Run many personas in parallel

Each `persona_seed` is an independent identity, so a pool of them scrapes concurrently
without correlating. Use the async API in Python and `Promise.all` in Node. Keep the pool
modest — concurrency is usually bounded by your proxies, not the browser.

### Python

```python
import asyncio
from chromiumfish.async_api import AsyncChromiumfish

async def fetch_title(seed: str, url: str) -> str:
    async with AsyncChromiumfish(persona_seed=seed) as browser:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        return await page.title()

async def main():
    jobs = [
        ("acct-1", "https://example.com/a"),
        ("acct-2", "https://example.com/b"),
        ("acct-3", "https://example.com/c"),
    ]
    titles = await asyncio.gather(*(fetch_title(s, u) for s, u in jobs))
    print(titles)

asyncio.run(main())
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

async function fetchTitle(seed, url) {
  const browser = await ChromiumFish({ personaSeed: seed });
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded" });
    return await page.title();
  } finally {
    await browser.close();
  }
}

const jobs = [
  ["acct-1", "https://example.com/a"],
  ["acct-2", "https://example.com/b"],
  ["acct-3", "https://example.com/c"],
];
const titles = await Promise.all(jobs.map(([s, u]) => fetchTitle(s, u)));
console.log(titles);
```

## Reuse a logged-in session

Log in once, save Playwright's `storage_state` (cookies + localStorage), and replay it on
later runs to skip the login. Keep the **same `persona_seed`** so the saved session and the
fingerprint stay consistent — a returning cookie on a brand-new device is itself a tell.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

# First run: log in, then save the session.
with Chromiumfish(persona_seed="acct-1") as browser:
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://example.com/login")
    # ... perform the login ...
    context.storage_state(path="acct-1.json")

# Later runs: restore it and you're already signed in.
with Chromiumfish(persona_seed="acct-1") as browser:
    context = browser.new_context(storage_state="acct-1.json")
    page = context.new_page()
    page.goto("https://example.com/account")
    print(page.title())
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

// First run: log in, then save the session.
let browser = await ChromiumFish({ personaSeed: "acct-1" });
let context = await browser.newContext();
let page = await context.newPage();
await page.goto("https://example.com/login");
// ... perform the login ...
await context.storageState({ path: "acct-1.json" });
await browser.close();

// Later runs: restore it and you're already signed in.
browser = await ChromiumFish({ personaSeed: "acct-1" });
context = await browser.newContext({ storageState: "acct-1.json" });
page = await context.newPage();
await page.goto("https://example.com/account");
console.log(await page.title());
await browser.close();
```

{: .note }
> `storage_state` carries cookies and localStorage, not the persona. The persona comes from
> the seed, so pass the same `persona_seed` both when you save and when you restore.

## Verify your persona

Before a real run, open a fingerprinting test page and confirm there are no automation or
tampering tells. [CreepJS](https://abrahamjuliot.github.io/creepjs/) is the strictest
freely-available check; `navigator.webdriver` should read `false` even under CDP.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="alpha-7") as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
    page.wait_for_timeout(4000)            # let the probes finish
    print(page.evaluate("navigator.webdriver"))  # -> False
    page.screenshot(path="creepjs.png", full_page=True)
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: "alpha-7" });
const page = await browser.newPage();
await page.goto("https://abrahamjuliot.github.io/creepjs/");
await page.waitForTimeout(4000);                 // let the probes finish
console.log(await page.evaluate("navigator.webdriver")); // -> false
await page.screenshot({ path: "creepjs.png", fullPage: true });
await browser.close();
```

Re-run with two different seeds and the visitor id should change; re-run with the same seed
and it should stay put. See [Personas](personas) for what's deterministic per seed.

## Route canvas/WebGL through the bridge

Canvas and WebGL **pixels** pass through clean by default (SwiftShader on headless Linux). If
a target hashes those reads, point the browser at the optional canvas-bridge with two flags
through `args`. Both flags are required, and the bridge must be running on a separate Windows
host — see [Canvas & WebGL bridge](canvas-bridge) for the full setup.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(
    persona_seed="alpha-7",
    args=[
        "--canvas-bridge-url=ws://your-win-host:8443/render",
        "--canvas-bridge-auth=user:secret",
    ],
) as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({
  personaSeed: "alpha-7",
  args: [
    "--canvas-bridge-url=ws://your-win-host:8443/render",
    "--canvas-bridge-auth=user:secret",
  ],
});
const page = await browser.newPage();
await page.goto("https://abrahamjuliot.github.io/creepjs/");
```

## High-friction targets

A persona spoofs the browser fingerprint, not the network. For sites with strict bot walls,
combine a pinned persona with a clean residential proxy and a matching timezone, and pace
your requests like a person would. If a target still reads canvas or WebGL as headless-Linux
SwiftShader, route those reads through the [canvas & WebGL bridge](canvas-bridge) — a
separate, optional render service on a real Windows GPU. When you're still blocked, work
through the [troubleshooting checklist](troubleshooting#im-still-getting-blocked).
