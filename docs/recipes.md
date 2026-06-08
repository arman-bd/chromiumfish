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

Pin one `persona_seed` per account and reuse it. The same seed reproduces the same
persona every run, so the site sees a returning user instead of a brand-new device each
visit. Keep your own mapping from `account_id` to seed.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

SEEDS = {"alice": 1001, "bob": 2002}

def scrape_account(account_id: str):
    with Chromiumfish(persona_seed=SEEDS[account_id]) as browser:
        page = browser.new_page()
        page.goto("https://example.com/account")
        return page.title()
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const SEEDS = { alice: 1001, bob: 2002 };

async function scrapeAccount(accountId) {
  const browser = await ChromiumFish({ personaSeed: SEEDS[accountId] });
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

For a single unlinkable session, generate a fresh random seed each run. Different seeds
produce uncorrelated personas, so two runs can't be tied together through the fingerprint.

### Python

```python
import random
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed=random.getrandbits(32)) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
    print(page.title())
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const seed = Math.floor(Math.random() * 2 ** 32);
const browser = await ChromiumFish({ personaSeed: seed });
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
    persona_seed=1001,
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
  personaSeed: 1001,
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

with Chromiumfish(persona_seed=1001) as browser:
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

const browser = await ChromiumFish({ personaSeed: 1001 });
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

with Chromiumfish(persona_seed=1001) as browser:
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

const browser = await ChromiumFish({ personaSeed: 1001 });
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

with Chromiumfish(persona_seed=1001, version="150.0.7844") as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

### Node

```javascript
import { ChromiumFish } from "chromiumfish";

const browser = await ChromiumFish({ personaSeed: 1001, version: "150.0.7844" });
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

## High-friction targets

A persona spoofs the browser fingerprint, not the network. For sites with strict bot walls,
combine a pinned persona with a clean residential proxy and a matching timezone, and pace
your requests like a person would.

{: .tip }
> If a target still reads canvas or WebGL as headless-Linux SwiftShader, the optional
> canvas-bridge answers those reads from a real Windows GPU. It runs as a separate render
> service outside the SDK and is configured at the browser level, not through any SDK option.
