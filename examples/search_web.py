#!/usr/bin/env python3
"""Web search demo: run a query and print the first result's URL.

Prereq: the demo webapp running ->  cd tests/webapp && .venv/bin/python app.py
"""
from chromiumfish import launch_agent

TASK = (
    "Go to http://127.0.0.1:8000/search, search for 'automation', "
    "and give me the first result's URL."
)

with launch_agent() as agent:
    result = agent.run_task(TASK)
    print(result.final_text)
