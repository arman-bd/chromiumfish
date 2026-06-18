---
title: AI Agent
nav_order: 4
---

# AI Agent
{: .no_toc }

1. TOC
{:toc}

---

ChromiumFish ships a **native, in-browser AI agent**: hand it a plain-language task and it
drives the page itself — perceive → think → act, in a loop — until the goal is done. The
agent lives **inside the C++ browser process** (it is *not* a Playwright script puppeteering
the page from outside), and it's driven by any **OpenAI-compatible** LLM you point it at.

```python
from chromiumfish import launch_agent

with launch_agent() as agent:
    result = agent.run_task("Search DuckDuckGo for 'chromiumfish' and give me the first result's URL.")
    print(result.final_text)
```

```ts
import { withAgent } from "chromiumfish";

const url = await withAgent({}, (agent) =>
  agent.runTask("Search DuckDuckGo for 'chromiumfish' and give me the first result's URL.")
       .then((r) => r.finalText));
console.log(url);
```

## What it does

- **Plain-language tasks.** "Log in with these credentials and tell me whose account you land
  on", "add the cheapest item to the cart and check out", "clear the bot-check and read me the
  headline". No selectors, no step scripting.
- **Real actions.** `click`, `type`, `scroll`, `navigate`, `select`, `read` (pull the page's
  text so it can summarize), `wait`, and `done`.
- **Reads links without clicking.** Each link's destination URL is in the agent's view, so it
  can answer "the first result's URL" without navigating to it.
- **Humanized input.** Typing happens key-by-key at a configurable [human cadence](#typing-speed);
  while it works it draws an action overlay — a cyan box around the target element and a red
  dot at the click point — **inside the page**, so you can watch it in a visible window.
- **Handles interstitials.** Cookie/consent modals and "verify you are human" checks are part
  of what it's trained to clear before continuing.

{: .note }
> The agent is the *only* feature that needs an LLM. The plain stealth browser
> (`Chromiumfish` / `ChromiumFish()`) needs no keys — see the [API reference](api).

## How it works

The agent runs a **perceive → think → act** loop entirely in the browser process, exposed
over a custom DevTools command, `Browser.agentRunTask`:

1. **Perceive.** Each turn the browser serializes the page's *interactive* controls — one per
   line as `[index]<role>label`, with each input's state (empty / value / checked / selected)
   — plus a one-line note saying whether the page changed since the last action. (Article/body
   text is *not* in this list; the agent issues a `read` action to pull page text when it needs
   to summarize or answer from content.)
2. **Think.** That observation is sent to your LLM, which replies with a small JSON plan: a
   `thought` and one or more `actions` to run in order.
3. **Act.** The browser executes those actions with humanized input, re-perceives, and loops —
   until the model emits `done` or it hits `maxSteps`.

```
your task ──▶ launch_agent ──▶ Browser.agentRunTask (CDP)
                                      │
                 ┌────────────────────┴─────────────────────┐
                 ▼                                            │
          perceive (interactive elements + change-note)      │
                 ▼                                            │
          think  (your OpenAI-compatible LLM → JSON actions)  │ loop ≤ maxSteps
                 ▼                                            │
          act    (click / type / read / navigate / …)  ──────┘
                 ▼
          done → final answer + resolved step plan
```

The SDK's `launch_agent` / `launchAgent` just starts a ChromiumFish build with the agent layer
and the `--agent-*` switches, then talks to it over CDP. `run_task` / `runTask` returns an
[`AgentResult`](#the-result) with the final answer and the resolved plan.

## Configuring the LLM

The agent needs an **OpenAI-compatible** endpoint. It's read from three environment variables,
which the SDK auto-loads from a nearby `.env`:

| Variable | Meaning |
|----------|---------|
| `OPENAI_API_KEY` | API key |
| `OPENAI_API_BASE` | Base URL — OpenAI, [OpenRouter](https://openrouter.ai), a local proxy, … |
| `OPENAI_API_MODEL` | Default model id |

`.env` (next to your script, or any parent directory):

```bash
OPENAI_API_BASE=https://openrouter.ai/api/v1/
OPENAI_API_KEY=sk-...
OPENAI_API_MODEL=qwen/qwen3.5-flash-02-23
```

The SDK forwards these to the browser as `--agent-llm-url` / `--agent-llm-key` /
`--agent-model`. Override precedence for the model: `run_task(model=…)` (per task) →
`launch_agent(model=…)` (per session) → `OPENAI_API_MODEL`.

{: .warning }
> With **no key configured**, the browser still launches, but `run_task` fails with
> *"agent LLM is not configured"*. Provide the env vars (or pass the switches via `extra_args`
> / `extraArgs`). Keep `.env` git-ignored. Note the key is passed as a process launch
> switch, so it is visible in the local process list (`ps`) to other users on the host.

## Typing speed

The agent types key-by-key. Control the cadence with `typing` — the default looks human;
faster settings trade realism for speed.

| Setting | Cadence | Feel |
|---------|---------|------|
| `"human"` (default) | 45ms / 110ms per key | ~75 WPM, natural |
| `"fast"` | 10ms / 18ms | brisk |
| `"instant"` | 0ms / 0ms | no inter-key delay |
| custom | `(keyDown, keyUp, longMultiplier)` | your own (numbers = ms) |

```python
with launch_agent(typing="fast") as agent:
    ...
```
```ts
await withAgent({ typing: "instant" }, async (agent) => { /* ... */ });
```

## The result

`run_task` / `runTask` returns an `AgentResult`:

| Field | Description |
|-------|-------------|
| `success` | Whether the agent reported the goal met. |
| `final_text` / `finalText` | The agent's answer. |
| `steps` | The resolved plan — each step tagged `recorded` / `replayed` / `healed`. |
| `summary()` | One-line digest, e.g. `ok \| 4 steps (0 replayed, 0 healed, 4 recorded)`. |

The `steps` array is a **replayable plan**: pass it back as `plan=` / `{ plan }` on a later
`run_task` and the agent replays it deterministically (descriptor-matching each step, only
calling the LLM to heal drift) — fast, cheap re-runs of a known flow.

## Pointing at a local build

By default the SDK fetches the published build. Point the agent at a local checkout's build
with `CHROME_BIN` (or `chrome=` / `chrome:`):

```bash
export CHROME_BIN=src/out/Release/ChromiumFish.app/Contents/MacOS/ChromiumFish   # macOS
# Linux: .../chrome
```

## Requirements

- **Python:** `pip install chromiumfish` (the agent client needs `websocket-client`:
  `pip install "chromiumfish[agent]"`).
- **Node:** `npm install chromiumfish`. The agent needs a WebSocket — Node 22+ has a global
  one; on Node &lt;22 add the optional `ws` package (`npm install ws`).

See the [examples](https://github.com/arman-bd/chromiumfish/tree/main/examples) for runnable
scripts, and the [Python](api/python#ai-agent) / [JavaScript](api/javascript#ai-agent) API
reference for every option.
