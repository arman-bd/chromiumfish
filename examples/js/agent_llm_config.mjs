// Configure the LLM in code — pass the key, base URL and model instead of a .env. (needs the demo app)
import { withAgent } from "chromiumfish";

const result = await withAgent(
  {
    apiKey: "sk-your-key-here",
    apiBase: "https://openrouter.ai/api/v1/",
    model: "qwen/qwen3.5-flash-02-23",
  },
  (agent) => agent.runTask("Go to http://127.0.0.1:8000/search, search for 'automation', and give me the first result's URL."),
);

console.log(result.finalText);
