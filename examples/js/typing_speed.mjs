#!/usr/bin/env node
// Control how fast the agent types.
//
// The agent types key-by-key. `typing` defaults to "human" (~75 WPM, natural);
// "fast" and "instant" go quicker, and a custom [keyDown, keyUp, longMultiplier]
// triple (numbers = ms) lets you dial it in. This runs the same task at three
// speeds so you can watch the difference in a visible window.
//
// LLM config (OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_API_MODEL) from a nearby .env.
// Prereq: cd tests/webapp && python app.py   (serves :8000)
// Run:    node examples/js/typing_speed.mjs
import { withAgent } from "chromiumfish";

const TASK =
  "Go to http://127.0.0.1:8000/todos, add a task 'buy oat milk', then tell me " +
  "how many tasks are left.";

for (const typing of ["human", "fast", "instant"]) {
  const out = await withAgent({ typing }, (agent) =>
    agent.runTask(TASK).then((r) => r.finalText),
  );
  console.log(`[${typing}] ${out}`);
}
