#!/usr/bin/env python3
"""Web search demo: print the first result's URL for a one-line task."""
from chromiumfish import launch_agent

TASK = "Search google for 'apple' and give me the first result's URL."

with launch_agent() as agent:
    print(agent.run_task(TASK).final_text)
