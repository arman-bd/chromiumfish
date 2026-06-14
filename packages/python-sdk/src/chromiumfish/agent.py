"""Native in-browser AI agent client.

Drives the fork's native ``Browser.agentRunTask`` CDP command on a running
ChromiumFish (launched with ``--remote-debugging-port`` and the ``--agent-*``
switches). Talks raw CDP over a WebSocket — the same path as
``__tools/agent_run.py`` — which avoids Playwright's ``connect_over_cdp``
context setup that this fork's CDP surface doesn't fully support.

This is the low-level client. For record/replay caching of whole flows, use
:class:`chromiumfish.flow.Flow`, which sits on top of this.

    from chromiumfish.agent import AgentClient

    client = AgentClient(port=9222)
    r = client.run_task("search for 'automation' and open the first result",
                        url="http://127.0.0.1:8000/search")
    print(r.success, r.final_text)
    # r.steps is the resolved plan you can persist + replay later.

Requires ``websocket-client`` (``pip install chromiumfish[agent]``).
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

# The agent's master/system prompt. Lives HERE in the library (not hardcoded in
# the browser binary) so it can be tuned without a Chromium rebuild; it is sent
# to the browser per task as ``Browser.agentRunTask``'s ``systemPrompt`` param,
# which the agent layer uses in place of its built-in default.
#
# Key behaviour: the final ``done`` answer is ONLY the value the task asked for
# — no prose, no labels — so callers get a clean result (e.g. just a URL).
AGENT_SYSTEM_PROMPT = (
    "You are an autonomous web-browsing agent operating directly inside the "
    "browser. Each turn you receive the interactive elements currently visible "
    "on the page, one per line:\n"
    "  [<index>]<role>label\n"
    "Roles: a (link), button, input, textarea, select, checkbox. Each input "
    "shows its STATE in brackets: [EMPTY; placeholder hint \"...\"] = empty, the "
    "hint is NOT a value, type into it; [value: \"...\"] = already contains that "
    "text; [filled]/[empty] = a password field; [checked]/[unchecked] = a "
    "checkbox; [selected: \"...\"]/[no selection] = a select (its choices follow "
    "as opts:[value=text, ...] — use one exact value). Disabled controls are "
    "marked (disabled). You also get a one-line note saying whether the page "
    "changed since your last action.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown):\n"
    "{\n"
    "  \"thought\": \"brief reasoning\",\n"
    "  \"actions\": [ <one or more action steps, run in order, in one shot> ]\n"
    "}\n"
    "Each step is an object: {\"action\": "
    "\"click|type|scroll|navigate|select|wait|done\", \"index\": <element "
    "index>, \"text\": \"to type\", \"enter\": true (type: press Enter), "
    "\"url\": \"https://...\" (navigate), \"value\": \"exact option value\" "
    "(select), \"direction\": \"down|up|left|right\" (scroll), \"seconds\": 1 "
    "(wait), \"success\": true and \"final\": \"<answer>\" (done)}.\n"
    "Put MULTIPLE steps in the array to do them in ONE shot (strongly preferred "
    "for speed): whenever you know the values, fill ALL fields AND click submit "
    "in a single response. Use a single step only when the next step truly "
    "depends on this one's result.\n\n"
    "Rules:\n"
    "- Use only indices in the CURRENT list; they are renumbered every step.\n"
    "- To submit a search or form, set \"enter\": true when typing, or click the "
    "submit/Continue button. Typing alone does not submit.\n"
    "- For a select, use action \"select\" with an exact value from its opts.\n"
    "- Do NOT repeat the same click twice in a row; if nothing changed, do "
    "something different (set enter:true, pick another element, wait, scroll).\n"
    "- RETURN ONLY WHAT WAS ASKED. When you are done, the \"final\" field must "
    "contain EXACTLY the value the task requested and NOTHING else — no "
    "sentences, no labels, no explanation, no quotes, no markdown. If asked for "
    "a URL, \"final\" is just the URL; for a name, just the name; for a number, "
    "just the number. Only when the task asks for a description/summary should "
    "\"final\" be a sentence.\n"
    "- Finish with a {\"action\":\"done\",\"success\":true,\"final\":\"...\"} "
    "step by itself; use success false only if the goal is genuinely impossible."
)


def _require_ws():
    try:
        from websocket import create_connection
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "the AI agent client needs the 'websocket-client' package; install "
            "it with `pip install chromiumfish[agent]` (or `pip install "
            "websocket-client`)."
        ) from exc
    return create_connection


def _http_get(url: str, timeout: float = 10.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)


@dataclass
class AgentResult:
    """Outcome of one agent task plus the resolved step plan."""

    success: bool
    final_text: str
    steps: list[dict]          # resolved plan; each step tagged with "status".
    replayed: bool = False     # whether a cached plan was supplied this run.

    @property
    def from_cache(self) -> int:
        """Number of steps replayed deterministically (no LLM call)."""
        return sum(1 for s in self.steps if s.get("status") == "replayed")

    @property
    def healed(self) -> int:
        """Number of steps the page had drifted on, re-resolved via the LLM."""
        return sum(1 for s in self.steps if s.get("status") == "healed")

    @property
    def recorded(self) -> int:
        """Number of steps resolved by the LLM on a fresh (non-replay) run."""
        return sum(1 for s in self.steps if s.get("status") == "recorded")

    def summary(self) -> str:
        return (
            f"{'ok' if self.success else 'fail'} | {len(self.steps)} steps "
            f"({self.from_cache} replayed, {self.healed} healed, "
            f"{self.recorded} recorded)"
        )


class _CDP:
    """Minimal synchronous CDP-over-WebSocket client."""

    def __init__(self, ws_url: str, timeout: float):
        create_connection = _require_ws()
        # suppress_origin: DevTools rejects WS connections that carry an Origin
        # header unless --remote-allow-origins matches; omitting it sidesteps that.
        self.ws = create_connection(
            ws_url, timeout=timeout, max_size=None, suppress_origin=True
        )
        self._id = 0

    def send(self, method: str, params: Optional[dict] = None, wait: bool = True):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        if not wait:
            return None
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def wait_event(self, method: str, timeout_s: float) -> None:
        end = time.time() + timeout_s
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                return
            if msg.get("method") == method:
                return

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


class AgentClient:
    """Connects to a running ChromiumFish CDP endpoint and runs agent tasks."""

    def __init__(self, port: int = 9222, *, host: str = "localhost",
                 timeout: float = 420.0):
        self.port = port
        self.host = host
        self.timeout = timeout

    def _pick_page(self) -> tuple[str, str]:
        """Return (target_id, ws_url), reusing a real page or opening one."""
        base = f"http://{self.host}:{self.port}"
        targets = _http_get(f"{base}/json")
        pages = [
            t for t in targets
            if t.get("type") == "page"
            and not t.get("url", "").startswith("chrome://")
            and t.get("webSocketDebuggerUrl")
        ]
        if pages:
            return pages[0]["id"], pages[0]["webSocketDebuggerUrl"]
        fresh = _http_get(f"{base}/json/new")
        return fresh["id"], fresh["webSocketDebuggerUrl"]

    def run_task(
        self,
        goal: str,
        *,
        url: Optional[str] = None,
        max_steps: int = 25,
        model: str = "",
        plan: Optional[list[dict]] = None,
        system_prompt: Optional[str] = AGENT_SYSTEM_PROMPT,
    ) -> AgentResult:
        """Run one agent task. If ``plan`` is given, the native agent REPLAYS it
        (descriptor match per step, LLM only to heal drift); otherwise it runs
        the LLM loop fresh. Returns the resolved steps either way.
        """
        target_id, ws_url = self._pick_page()
        cdp = _CDP(ws_url, self.timeout)
        try:
            cdp.send("Page.enable")
            if url and url != "about:blank":
                cdp.send("Page.navigate", {"url": url})
                cdp.wait_event("Page.loadEventFired", 20)
                time.sleep(0.5)
            params: dict[str, Any] = {
                "targetId": target_id, "goal": goal, "maxSteps": max_steps,
            }
            if model:
                params["model"] = model
            if plan:
                params["planJson"] = json.dumps(plan)
            if system_prompt:
                # Honored by browsers whose agent layer reads it; older builds
                # ignore the unknown param and use their built-in prompt.
                params["systemPrompt"] = system_prompt
            res = cdp.send("Browser.agentRunTask", params) or {}
            try:
                steps = json.loads(res.get("stepsJson") or "[]")
            except Exception:
                steps = []
            return AgentResult(
                success=bool(res.get("success")),
                final_text=res.get("finalText", ""),
                steps=steps if isinstance(steps, list) else [],
                replayed=bool(plan),
            )
        finally:
            cdp.close()


def _load_dotenv() -> None:
    """Load ``KEY=VALUE`` lines from the nearest ``.env`` (cwd or a parent) into
    the environment, without overriding values already set."""
    for d in (Path.cwd(), *Path.cwd().parents):
        env = d / ".env"
        if not env.is_file():
            continue
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
        return


@contextlib.contextmanager
def launch_agent(
    *,
    port: int = 9222,
    chrome: Optional[os.PathLike | str] = None,
    load_dotenv: bool = True,
    extra_args: Optional[list[str]] = None,
    timeout: float = 30.0,
) -> Iterator["AgentClient"]:
    """Launch a local ChromiumFish with the AI agent layer and connect to it.

    Yields a connected :class:`AgentClient`; the browser is shut down and its
    temp profile removed when the ``with`` block exits::

        with launch_agent() as agent:
            print(agent.run_task("...").final_text)

    LLM config is read from ``OPENAI_API_BASE`` / ``OPENAI_API_KEY`` /
    ``OPENAI_API_MODEL`` (a nearby ``.env`` is loaded automatically). The binary
    is ``chrome=`` / the ``CHROME_BIN`` env var / the published build.
    """
    if load_dotenv:
        _load_dotenv()
    if chrome is None:
        chrome = os.environ.get("CHROME_BIN")
    if chrome is None:
        from .fetch import binary_path  # lazy: avoids the fetch import otherwise
        chrome = binary_path()
    profile = tempfile.mkdtemp(prefix="cf-agent-")
    proc = subprocess.Popen(
        [
            str(chrome),
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--disable-actor-safety-checks",  # let the agent act unattended
            "--no-first-run", "--no-default-browser-check",
            f"--agent-llm-url={os.environ.get('OPENAI_API_BASE', '')}",
            f"--agent-llm-key={os.environ.get('OPENAI_API_KEY', '')}",
            f"--agent-model={os.environ.get('OPENAI_API_MODEL', '')}",
            *(extra_args or []),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + timeout
        while True:
            try:
                urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=1)
                break
            except Exception:
                if time.time() > deadline:
                    raise RuntimeError("ChromiumFish did not expose its CDP endpoint in time")
                time.sleep(0.5)
        yield AgentClient(port=port)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
