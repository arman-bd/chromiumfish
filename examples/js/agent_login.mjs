// Log in to the demo app and report whose account the agent lands on. (needs the demo app + an LLM in .env)
import { launchAgent } from "chromiumfish";

const { agent, close } = await launchAgent();
try {
  const result = await agent.runTask(
    "Go to http://127.0.0.1:8000/login, sign in with demo@bytetunnels.test / password123, and tell me whose account you land on.",
  );
  console.log(result.finalText);
} finally {
  await close();
}
