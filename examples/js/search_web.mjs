#!/usr/bin/env node
// One-line web search via the AI agent (JavaScript).
//
// Uses withAgent(), which launches the build, connects, runs your function, and
// cleans up on exit — the ergonomic equivalent of Python's `with launch_agent()`.
//
// LLM config (OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_API_MODEL) from a nearby .env.
// Prereq: cd tests/webapp && python app.py   (serves :8000)
// Run:    node examples/js/search_web.mjs
import { withAgent } from "chromiumfish";

const TASK =
  "Go to http://127.0.0.1:8000/search, search for 'automation', and give me " +
  "the first result's URL.";

const url = await withAgent({}, (agent) =>
  agent.runTask(TASK).then((r) => r.finalText),
);
console.log(url);
