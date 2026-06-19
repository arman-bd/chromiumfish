// Search the demo app and print the first result's URL. (needs the demo app + an LLM in .env)
import { withAgent } from "chromiumfish";

const result = await withAgent({}, (agent) =>
  agent.runTask("Go to http://127.0.0.1:8000/search, search for 'automation', and give me the first result's URL."),
);

console.log(result.finalText);
