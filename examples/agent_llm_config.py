"""Configure the LLM in code — pass the key, base URL and model instead of a .env. (needs the demo app)"""
from chromiumfish import launch_agent

with launch_agent(
    api_key="sk-your-key-here",
    api_base="https://openrouter.ai/api/v1/",
    model="qwen/qwen3.5-flash-02-23",
) as agent:
    result = agent.run_task("Go to http://127.0.0.1:8000/search, search for 'automation', and give me the first result's URL.")
    print(result.final_text)
