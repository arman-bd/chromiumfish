#!/usr/bin/env python3
"""Chained tasks: each instruction uses the previous one's output (shared session)."""
from pathlib import Path

from chromiumfish import launch_agent

BLOG = "https://blog.python.org/"
OUT = Path("blog_summary.txt")

with launch_agent() as agent:
    # 1. find the first post's URL
    post = agent.run_task(f"Go to {BLOG} and give me the URL of the latest blog post.")
    url = post.final_text.strip()

    # 2. next instruction built from task 1's output: visit it and summarize
    summary = agent.run_task(f"Go to {url} and summarize the post in 3-4 sentences.")

    # 3. save the chained output to a text file
    OUT.write_text(f"{url}\n\n{summary.final_text}\n")
    print(f"saved {OUT}")
    print(summary.final_text)
