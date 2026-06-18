# examples

Small scripts showing how to drive ChromiumFish, in two flavors:

- **Native AI agent** (`run_agent.py`, `search_web.py`) — hand it a plain-language
  task; it perceives + acts inside the browser process. Needs an LLM (`.env`).
- **Plain Playwright** (`playwright_*.py`) — drive the stealth browser yourself
  with ordinary Playwright, under a per-seed persona. No LLM needed.

## `run_agent.py` — native AI agent

Launches a ChromiumFish build with the agent layer, hands the agent a
plain-language task (the agent navigates to the URL named *in the task* itself),
prints the outcome, and kills the browser on exit. As it works it draws its
action overlay — a cyan box around the element + a red dot at the click point —
**inside the page**, so keep the window visible to watch.

```sh
# 1. the demo webapp the task visits
cd tests/webapp && .venv/bin/python app.py        # serves :8000

# 2. install the SDK, then run the example
pip install -e packages/python-sdk                # or: PYTHONPATH=packages/python-sdk/src
python3 examples/run_agent.py
```

LLM config (`OPENAI_API_BASE` / `OPENAI_API_KEY` / `OPENAI_API_MODEL`) is read
from `.env` at the repo root. The example fetches the published build by default;
point it at a local build with `CHROME_BIN=src/out/Release/ChromiumFish.app/Contents/MacOS/ChromiumFish`.

Edit the `TASK` string to send the agent anywhere.

## `search_web.py` — one-line web search

The whole demo, using the `launch_agent()` context manager (it launches the
build, connects, and cleans up on exit):

```python
from chromiumfish import launch_agent

TASK = "Go to http://127.0.0.1:8000/search, search for 'automation', and give me the first result's URL."

with launch_agent() as agent:
    print(agent.run_task(TASK).final_text)
```

```sh
python3 examples/search_web.py
```

## `playwright_*.py` — plain Playwright (the stealth browser)

`Chromiumfish` / `AsyncChromiumfish` wrap `playwright.chromium.launch` at the
ChromiumFish build and apply a `persona_seed`; they hand back a normal Playwright
`Browser`, so all of Playwright works as usual.

```python
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="alpha-7") as browser:   # also: headless=, proxy=,
    page = browser.new_page()                            # window_size=, timezone="auto"
    page.goto("https://example.com/")
    print(page.title())
```

```sh
pip install chromiumfish        # pulls Playwright; the published build is fetched on first run
python3 examples/playwright_basic.py        # open a page, print its title
python3 examples/playwright_fingerprint.py  # what a page sees: a Windows persona; per-seed entropy
python3 examples/playwright_screenshot.py   # full-page PNG -> screenshot.png
python3 examples/playwright_async.py        # AsyncChromiumfish: fetch several pages concurrently
```

These don't need an LLM or `.env`. Unlike the agent examples, the Playwright
wrapper always uses the fetched/installed build (it doesn't read `CHROME_BIN`).
