"""Search the demo app and print the first result's URL. (needs the demo app + an LLM in .env)"""
from chromiumfish import launch_agent

with launch_agent() as agent:
    result = agent.run_task(
        "Go to http://127.0.0.1:8000/search, search for 'automation', "
        "and give me the first result's URL."
    )
    print(result.final_text)
