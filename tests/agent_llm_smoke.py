#!/usr/bin/env python3
"""Live smoke test for the agent's LLM brain (no browser build required).

Replicates exactly what chrome/browser/ai_agent/llm_client.cc + agent_controller.cc
send: the real system prompt + a representative page observation, POSTed to the
OpenAI-compatible endpoint configured in ../.env (OPENAI_API_BASE/KEY/MODEL).
Verifies the model returns a single JSON action object the C++ parser accepts.

Usage:  python3 tests/agent_llm_smoke.py
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# --- exact system prompt from agent_controller.cc (kSystemPrompt) ---
SYSTEM_PROMPT = (
    "You are an autonomous web-browsing agent operating directly inside the "
    "browser. Each turn you are given the list of interactive elements on the "
    "current page. Each line looks like:\n"
    "  [3]<button>Sign in\n"
    "where 3 is the element index you reference in actions.\n\n"
    "Respond with ONLY a single JSON object (no prose, no markdown), shaped:\n"
    "{\n"
    '  "thought": "brief reasoning",\n'
    '  "action": "click|type|scroll|navigate|select|wait|done",\n'
    '  "index": <element index, for click/type/select/scroll-on-element>,\n'
    '  "text": "text to type (for type)",\n'
    '  "enter": true,            // optional, press Enter after typing\n'
    '  "url": "https://...",    // for navigate\n'
    '  "value": "option value", // for select\n'
    '  "direction": "down|up|left|right", // for scroll\n'
    '  "seconds": 1,             // for wait\n'
    '  "success": true,          // for done\n'
    '  "final": "summary of result" // for done\n'
    "}\n"
    "Only use element indices that appear in the current list; they change "
    "every step. When the task is complete (or impossible), use action "
    '"done".'
)

# A representative observation as page_serializer.cc would emit for /login.
OBSERVATION = (
    "Step 1/25.\n"
    "Current URL: http://127.0.0.1:8000/login\n"
    "Interactive elements (4):\n"
    "[1]<input>Email\n"
    "[2]<input>Password\n"
    "[3]<button>Sign in\n"
    "[4]<button>Autofill demo credentials\n"
    "Respond with the next action as a single JSON object."
)

GOAL = "Log in with the demo credentials, then confirm you're on the account page."

KNOWN_ACTIONS = {"click", "type", "scroll", "navigate", "select", "wait", "done"}


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def parse_action_json(content: str):
    """Mirror agent_controller.cc ParseActionJson: first balanced {...}."""
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(content[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    env = load_env(repo / ".env")
    base = env.get("OPENAI_API_BASE", "").rstrip("/")
    key = env.get("OPENAI_API_KEY", "")
    model = env.get("OPENAI_API_MODEL", "")
    if not (base and key and model):
        print("ERROR: OPENAI_API_BASE/KEY/MODEL missing in .env", file=sys.stderr)
        return 1

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {GOAL}"},
            {"role": "user", "content": OBSERVATION},
        ],
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chromiumfish.com",
            "X-Title": "ChromiumFish Agent",
        },
        method="POST",
    )
    print(f"-> {base}/chat/completions  model={model}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001
        print(f"REQUEST FAILED: {e}", file=sys.stderr)
        return 2

    content = payload["choices"][0]["message"].get("content", "")
    print("\n--- model content ---")
    print(content)
    print("---------------------\n")

    action = parse_action_json(content)
    if not action:
        print("FAIL: response did not contain a parseable JSON object")
        return 3
    verb = action.get("action")
    if verb not in KNOWN_ACTIONS:
        print(f"FAIL: unknown/missing action verb: {verb!r}")
        return 4
    # Index actions must reference a listed element (1..4 here).
    if verb in {"click", "type", "select"}:
        idx = action.get("index")
        if not isinstance(idx, int) or not (1 <= idx <= 4):
            print(f"FAIL: action {verb!r} has out-of-range index {idx!r}")
            return 5

    print(f"PASS: model returned a valid action -> {verb} {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
