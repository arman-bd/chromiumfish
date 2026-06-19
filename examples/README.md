# Examples

Small scripts that drive ChromiumFish. Two kinds:

- **AI agent** (`agent_*`) — hand the in-browser agent a plain-language task. Needs an
  OpenAI-compatible LLM, via a nearby `.env` (`OPENAI_API_KEY` / `OPENAI_API_BASE` /
  `OPENAI_API_MODEL`) or passed to `launch_agent(...)` / `launchAgent(...)` directly.
- **Playwright** (`playwright_*`) — drive the stealth browser yourself under a persona. No LLM.

Most agent examples visit the bundled demo app, so start it first:

```sh
cd tests/webapp && python app.py     # serves http://127.0.0.1:8000
```

## Python

| File | What it does |
|------|--------------|
| `agent_login.py` | Agent logs in and reports whose account it landed on. |
| `agent_search.py` | Agent searches and returns the first result's URL. |
| `agent_chained_tasks.py` | Two tasks in one session — the second uses the first's answer. |
| `agent_llm_config.py` | Pass the LLM key / base URL / model in code instead of a `.env`. |
| `playwright_open_page.py` | Open a page under a seeded persona, print its title. |
| `playwright_concurrent_pages.py` | Fetch several pages at once (async API). |
| `playwright_fingerprint.py` | Print what a page sees for two seeds. |
| `playwright_screenshot.py` | Save a full-page screenshot. |

```sh
python examples/agent_login.py
python examples/playwright_open_page.py
```

The `playwright_*` scripts need no LLM or `.env`. Point the agent examples at a local build
with `CHROME_BIN=…/ChromiumFish`.

## JavaScript (`js/`)

`npm install chromiumfish` (on Node &lt;22 also `npm i ws`), same `.env`, then:

| File | What it does |
|------|--------------|
| `js/agent_login.mjs` | Agent logs in and reports the account. |
| `js/agent_search.mjs` | One-line search via `withAgent()`. |
| `js/agent_typing_speed.mjs` | Same task at human / fast / instant typing. |
| `js/agent_llm_config.mjs` | Pass the LLM key / base URL / model in code instead of a `.env`. |

```sh
node examples/js/agent_login.mjs
```
