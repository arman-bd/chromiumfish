"""Log in to the demo app and report whose account the agent lands on. (needs the demo app + an LLM in .env)"""
from chromiumfish import launch_agent

task = (
    "Go to http://127.0.0.1:8000/login, sign in with demo@bytetunnels.test / "
    "password123, and tell me whose account you land on."
)

with launch_agent() as agent:
    result = agent.run_task(task)
    print(result.final_text)
