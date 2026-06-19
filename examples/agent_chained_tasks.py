"""Two agent tasks in one session — the second uses the first's answer. (needs the demo app + an LLM in .env)"""
from chromiumfish import launch_agent

with launch_agent() as agent:
    found = agent.run_task("Go to http://127.0.0.1:8000/shop and give me the URL of the first product.")
    url = found.final_text.strip()

    summary = agent.run_task(f"Go to {url} and summarize the product in 3-4 sentences.")
    print(url)
    print(summary.final_text)
