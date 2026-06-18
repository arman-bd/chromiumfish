#!/usr/bin/env node
// Run the native in-browser AI agent from a plain-language task (JavaScript).
//
// Launches a ChromiumFish build with the agent layer, hands the agent a task that
// *includes the URL to visit* (the agent navigates there itself), and prints what
// it did. As it works it draws its action overlay (a cyan box around the target
// element + a red dot at the click point) INSIDE the page, so keep the window
// visible to watch.
//
// LLM config (OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_API_MODEL) is read from a
// nearby .env. Point at a local build with CHROME_BIN=...
//
// Prereq: the demo webapp running ->  cd tests/webapp && python app.py   (serves :8000)
// Run:    node examples/js/run_agent.mjs
import { launchAgent } from "chromiumfish";

const TASK =
  "Go to http://127.0.0.1:8000/login, sign in with email " +
  "demo@bytetunnels.test and password password123, then tell me whose " +
  "account you landed on.";

const { agent, close } = await launchAgent(); // typing: "human" by default
try {
  const result = await agent.runTask(TASK, { maxSteps: 10 });
  console.log(result.summary());
  console.log(result.finalText);
} finally {
  await close();
}
