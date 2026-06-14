# examples

Small scripts showing how to drive ChromiumFish.

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

TASK = "Search duckduckgo.com for 'apple' and give me the first result's URL."

with launch_agent() as agent:
    print(agent.run_task(TASK).final_text)
```

```sh
python3 examples/search_web.py
```
