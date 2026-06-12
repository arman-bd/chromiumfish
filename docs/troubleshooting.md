---
title: Troubleshooting
nav_order: 7
---

# Troubleshooting
{: .no_toc }

1. TOC
{:toc}

---

Common issues and how to resolve them. If something here doesn't cover your case,
the SDK is a thin wrapper over Playwright, so most problems are ordinary
Playwright problems — its [docs](https://playwright.dev) apply unchanged.

## The first launch is slow or seems to hang

The first launch (or `chromiumfish fetch`) downloads the browser build — a few
hundred MB — and caches it under `~/.cache/chromiumfish/<version>/`. That one-time
download is what you're waiting on; later runs reuse the cache and start fast.

Pre-fetch it explicitly so the cost isn't hidden inside your first script run:

```bash
chromiumfish fetch        # Python
npx chromiumfish fetch    # Node
```

Print where the binary landed, or wipe the cache to force a clean re-download:

```bash
chromiumfish path     # show the cached binary path
chromiumfish clear    # remove all cached builds
```

## The download fails or the archive won't verify

The SDK checks the build's SHA-256 against the published checksum and refuses a
mismatch, so a verification error usually means a truncated or proxied download
rather than a bad build. Retry on a clean network, and if you're behind a
corporate proxy, make sure `pip` / `npm` and the runtime can reach
`github.com` and its release-asset CDN. To pin and cache a specific build out of
band, set `CHROMIUMFISH_VERSION` and run `chromiumfish fetch` once.

## Linux: "running as root without --no-sandbox" or a sandbox crash

The SDK already launches with `--no-sandbox` (and `--no-zygote`,
`--disable-dev-shm-usage`) in its base arguments, which is what you want on most
CI and container hosts. If you still hit a crash on a minimal image, you're
usually missing shared libraries Chromium needs. Install the Playwright system
dependencies once:

```bash
npx playwright install-deps chromium
# or, Debian/Ubuntu, by hand:
sudo apt-get install -y libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2
```

You do **not** run `playwright install` — ChromiumFish brings its own browser;
`install-deps` only pulls the OS libraries.

## I can't see anything — how do I watch it run?

Launches are headless by default. Pass `headless=False` (Python) /
`headless: false` (Node) to open a visible window while you debug a selector or a
login flow:

```python
with Chromiumfish(persona_seed="alpha-7", headless=False) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
    page.pause()   # opens the Playwright Inspector
```

`page.pause()` drops you into the Playwright Inspector so you can step through and
pick selectors interactively. Headful mode needs a display; on a headless server
run it under `xvfb-run`.

## My timezone doesn't match my proxy

A clock that disagrees with the exit IP is an easy tell. Set `timezone="auto"` and
the SDK resolves the egress IP (through your proxy, if set) to an IANA zone via the
ip2tz DB and applies it:

```python
with Chromiumfish(
    persona_seed="alpha-7",
    proxy={"server": "http://proxy.example.com:8000"},
    timezone="auto",
) as browser:
    ...
```

If `"auto"` resolves to nothing, the egress probe couldn't reach the network or the
IP isn't in the DB — pass an explicit IANA name like `timezone="Europe/Berlin"`
instead. You can check what an IP resolves to without launching a browser:

```python
from chromiumfish import lookup_timezone, resolve_timezone
print(lookup_timezone("8.8.8.8"))  # "America/Los_Angeles"
print(resolve_timezone())          # your egress IP's zone
```

## A site still reads me as canvas/WebGL software rendering

That's expected: canvas and WebGL **pixels** are clean by default and aren't
spoofed in the engine, so on headless Linux they're SwiftShader's software output.
If a specific target hashes those reads, route them through the optional
[canvas & WebGL bridge](canvas-bridge). Everything else in the persona — UA, Client
Hints, fonts, audio, the WebGL vendor/renderer string — is already native.

## I'm still getting blocked

A persona spoofs the **browser fingerprint**, not your network identity or
behaviour. When a coherent fingerprint isn't enough, the block is almost always
coming from one of these:

- **IP reputation.** Datacenter IPs get flagged regardless of fingerprint. Pair the
  persona with a clean residential proxy, and keep the proxy's geo consistent with
  the persona's locale and timezone.
- **Behaviour.** Requests that are too fast, too regular, or skip the pages a human
  would visit read as automation. Pace requests and follow realistic navigation.
- **Session freshness.** A brand-new cold session with no cookies is more suspect on
  some targets. Reuse a warmed-up [storage state](recipes#reuse-a-logged-in-session)
  where it makes sense.

See [Personas](personas) for how identity, network, and behaviour fit together.

## Verifying the persona looks right

Open a fingerprinting test page and confirm there are no automation or tampering
tells. [CreepJS](https://abrahamjuliot.github.io/creepjs/) is the strictest
freely-available check:

```python
with Chromiumfish(persona_seed="alpha-7") as browser:
    page = browser.new_page()
    page.goto("https://abrahamjuliot.github.io/creepjs/")
    page.wait_for_timeout(4000)
    page.screenshot(path="creepjs.png", full_page=True)
```

`navigator.webdriver` should be `false` even under CDP, and there should be no
`cdc_` automation artifacts. See the [verify-your-persona recipe](recipes#verify-your-persona)
for the same flow in both languages.
