#!/usr/bin/env python3
"""Web search demo: print the first result's URL for a query."""
from chromiumfish import launch_agent

TASK = "Search duckduckgo for 'bytetunnels' and give me the first result's URL."

with launch_agent() as agent:
    result = agent.run_task(TASK)
    print(result.final_text)
