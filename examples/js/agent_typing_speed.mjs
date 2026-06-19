// Run the same task at three typing speeds. (needs the demo app + an LLM in .env)
import { withAgent } from "chromiumfish";

const task = "Go to http://127.0.0.1:8000/todos, add a task 'buy oat milk', then tell me how many tasks are left.";

for (const typing of ["human", "fast", "instant"]) {
  const result = await withAgent({ typing }, (agent) => agent.runTask(task));
  console.log(`${typing}: ${result.finalText}`);
}
