#!/usr/bin/env python3
"""Run the native in-browser AI agent from a plain-language task.

Launches a ChromiumFish build with the agent layer, hands the agent a task that
*includes the URL to visit* (the agent navigates there itself), and prints what
it did. As it works it draws its action overlay (a cyan box around the target
element + a red dot at the click point) INSIDE the page, so keep the window
visible to watch. The browser is killed on exit.

LLM config (OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_API_MODEL) is read from a
nearby .env. Point at a local build with CHROME_BIN=...

Prereq: the demo webapp running ->  cd tests/webapp && .venv/bin/python app.py
Run:    python3 examples/run_agent.py
"""
from chromiumfish import launch_agent

TASK = (
    "Go to http://127.0.0.1:8000/login, sign in with email "
    "demo@bytetunnels.test and password password123, then tell me whose "
    "account you landed on."
)

with launch_agent() as agent:
    result = agent.run_task(TASK, max_steps=10)
    print(result.summary())
    print(result.final_text)
