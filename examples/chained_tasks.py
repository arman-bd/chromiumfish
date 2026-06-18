#!/usr/bin/env python3
"""Chained tasks: each instruction uses the previous one's output (shared session).

Prereq: the demo webapp running ->  cd tests/webapp && .venv/bin/python app.py
"""
from pathlib import Path

from chromiumfish import launch_agent

SHOP = "http://127.0.0.1:8000/shop"
OUT = Path("product_summary.txt")

with launch_agent() as agent:
    # 1. find the first product's URL
    first = agent.run_task(f"Go to {SHOP} and give me the URL of the first product.")
    url = first.final_text.strip()

    # 2. next instruction built from task 1's output: visit it and summarize
    summary = agent.run_task(f"Go to {url} and summarize the product in 3-4 sentences.")

    # 3. save the chained output to a text file
    OUT.write_text(f"{url}\n\n{summary.final_text}\n")
    print(f"saved {OUT}")
    print(summary.final_text)
