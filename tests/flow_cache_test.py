#!/usr/bin/env python3
"""End-to-end test for the native AI agent's record/replay CACHING layer.

Exercises chromiumfish.flow.Flow against a *running* ChromiumFish (CDP :9222,
launched with the --agent-* switches) and the ByteTunnels webapp (:8000), and
proves the cache actually saves LLM calls — not just that it returns steps.

Four phases, each asserting both the step-status accounting (replayed / healed /
recorded) AND the real number of LLM round-trips, counted from the agent I/O log
(`--agent-log-file`, one `==== step N SENT ====` marker per round-trip):

  1. RECORD       fresh run, no cache      -> recorded>0, replayed==0, plan saved
  2. REPLAY       clean cache hit          -> replayed==all, recorded==0, 0 LLM calls
  3. HEAL         one descriptor corrupted -> >=1 healed, >=1 LLM call, plan re-saved
  4. RE-REPLAY    after self-heal          -> replayed==all again, 0 LLM calls

Usage:
    python3 tests/flow_cache_test.py
    AGENT_LOG=/tmp/chromiumfish-agent-io.log PORT=9222 WEBAPP=http://127.0.0.1:8000 \
        python3 tests/flow_cache_test.py

Exit code 0 = all phases passed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Use the in-repo SDK without requiring an install.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "python-sdk" / "src"))

from chromiumfish.agent import AgentClient  # noqa: E402
from chromiumfish.flow import Flow  # noqa: E402

PORT = int(os.environ.get("PORT", "9222"))
WEBAPP = os.environ.get("WEBAPP", "http://127.0.0.1:8000").rstrip("/")
AGENT_LOG = Path(os.environ.get("AGENT_LOG", "/tmp/chromiumfish-agent-io.log"))

# A short, stable, IDEMPOTENT flow: the search box is at the top of the page
# (above the fold, so both record's Actor click and replay's humanized click
# resolve cleanly) and search has NO server-side state, so every run starts from
# an identical DOM and a clean replay never legitimately drifts. (An earlier
# version added a to-do each run, which accumulated hundreds of identical rows
# and made the model loop -- never do a flow with growing side effects here.)
# Overridable via env to retarget other scenarios.
FLOW_NAME = os.environ.get("FLOW_NAME", "cachetest-search")
GOAL = os.environ.get(
    "FLOW_GOAL",
    "Type 'wireless headphones' into the search box, then submit the search.",
)
START_URL = os.environ.get("FLOW_URL", f"{WEBAPP}/search")


def llm_calls() -> int:
    """Number of LLM round-trips recorded so far (counts SENT markers)."""
    try:
        return AGENT_LOG.read_text(errors="replace").count(" SENT ====")
    except FileNotFoundError:
        return -1  # log unavailable


class Check:
    def __init__(self):
        self.failures: list[str] = []

    def ok(self, cond: bool, msg: str):
        mark = "PASS" if cond else "FAIL"
        print(f"    [{mark}] {msg}")
        if not cond:
            self.failures.append(msg)


def banner(title: str):
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")


def show(tag: str, r, dcalls):
    delta = "n/a" if dcalls < 0 else str(dcalls)
    print(f"  {tag}: {r.summary()}  | LLM round-trips this run: {delta}")
    print(f"        final: {r.final_text[:120]!r}")


def main() -> int:
    log_available = llm_calls() >= 0
    if not log_available:
        print(f"WARNING: agent log {AGENT_LOG} not found — LLM-call counts "
              f"unverifiable; status-accounting still checked.\n")

    flow_dir = Path(tempfile.mkdtemp(prefix="cf-flowcache-"))
    flow = Flow(FLOW_NAME, client=AgentClient(port=PORT), flow_dir=flow_dir)
    chk = Check()
    print(f"flow dir : {flow_dir}\nstart url: {START_URL}\nagent log: {AGENT_LOG}")

    # ---------- Phase 1: RECORD (cold cache) ----------
    banner("PHASE 1 — RECORD (cold cache, full LLM loop)")
    flow.clear()
    chk.ok(not flow.exists(), "no cache file before record")
    before = llm_calls()
    r1 = flow.run(GOAL, url=START_URL)
    d1 = llm_calls() - before if log_available else -1
    show("record", r1, d1)
    chk.ok(r1.success, "record run succeeded")
    chk.ok(r1.recorded > 0, f"record produced LLM-resolved steps (recorded={r1.recorded})")
    chk.ok(r1.from_cache == 0, f"record replayed nothing (replayed={r1.from_cache})")
    chk.ok(flow.exists(), "cache file written to disk after record")
    if log_available:
        chk.ok(d1 > 0, f"record made real LLM round-trips ({d1})")
    plan = flow.load() or []
    chk.ok(len(plan) > 0, f"saved plan is non-empty ({len(plan)} steps)")
    chk.ok(all("status" in s for s in plan), "every saved step carries a status")
    chk.ok(any(s.get("role") for s in plan),
           "saved plan has durable {role,name,ordinal} descriptors")

    # ---------- Phase 2: REPLAY (warm cache) ----------
    banner("PHASE 2 — REPLAY (warm cache, expect ZERO LLM calls)")
    before = llm_calls()
    r2 = flow.run(GOAL, url=START_URL)
    d2 = llm_calls() - before if log_available else -1
    show("replay", r2, d2)
    chk.ok(r2.success, "replay run succeeded")
    chk.ok(r2.from_cache == len(r2.steps) and r2.from_cache > 0,
           f"every step served from cache (replayed={r2.from_cache}/{len(r2.steps)})")
    chk.ok(r2.recorded == 0, f"replay invoked no fresh recording (recorded={r2.recorded})")
    chk.ok(r2.healed == 0, f"clean page needed no healing (healed={r2.healed})")
    if log_available:
        chk.ok(d2 == 0, f"replay made ZERO LLM round-trips (was {d2}) — the cache win")

    # ---------- Phase 3: HEAL (corrupt one descriptor) ----------
    banner("PHASE 3 — HEAL (corrupt one descriptor, expect LLM heal of just that step)")
    plan = flow.load() or []
    # Corrupt the first non-'done' step's target name so MatchDescriptor misses
    # and the native loop must heal that single slot via the LLM.
    corrupted_idx = next(
        (i for i, s in enumerate(plan) if s.get("action") not in ("done", None)
         and s.get("role")),
        None,
    )
    chk.ok(corrupted_idx is not None, "found a targeted step to corrupt")
    if corrupted_idx is not None:
        orig_name = plan[corrupted_idx].get("name")
        plan[corrupted_idx]["name"] = "ZZ-nonexistent-target-ZZ"
        flow.save(GOAL, plan)
        print(f"    corrupted step {corrupted_idx}: name {orig_name!r} -> "
              f"{plan[corrupted_idx]['name']!r}")
        before = llm_calls()
        r3 = flow.run(GOAL, url=START_URL)
        d3 = llm_calls() - before if log_available else -1
        show("heal", r3, d3)
        chk.ok(r3.success, "healed run succeeded")
        chk.ok(r3.healed >= 1, f"drifted step was healed (healed={r3.healed})")
        chk.ok(r3.from_cache >= 1, f"undrifted steps still replayed (replayed={r3.from_cache})")
        if log_available:
            chk.ok(d3 >= 1, f"healing spent real LLM round-trips ({d3})")
        healed_plan = flow.load() or []
        chk.ok(all(s.get("name") != "ZZ-nonexistent-target-ZZ" for s in healed_plan),
               "self-healed plan was written back (corruption gone)")

    # ---------- Phase 4: RE-REPLAY (after self-heal) ----------
    banner("PHASE 4 — RE-REPLAY (after self-heal, expect ZERO LLM calls again)")
    before = llm_calls()
    r4 = flow.run(GOAL, url=START_URL)
    d4 = llm_calls() - before if log_available else -1
    show("re-replay", r4, d4)
    chk.ok(r4.success, "re-replay succeeded")
    chk.ok(r4.from_cache == len(r4.steps) and r4.from_cache > 0,
           f"cache fully repaired (replayed={r4.from_cache}/{len(r4.steps)})")
    chk.ok(r4.healed == 0, f"no residual drift (healed={r4.healed})")
    if log_available:
        chk.ok(d4 == 0, f"re-replay made ZERO LLM round-trips (was {d4})")

    # ---------- Summary ----------
    banner("RESULT")
    if log_available:
        print(f"  LLM round-trips:  record={d1}  replay={d2}  heal={d3 if corrupted_idx is not None else 'n/a'}  re-replay={d4}")
        if d1 > 0:
            saved = d1 - d2
            print(f"  Cache eliminated {saved}/{d1} LLM round-trips on a warm hit.")
    if chk.failures:
        print(f"\n  {len(chk.failures)} CHECK(S) FAILED:")
        for f in chk.failures:
            print(f"    - {f}")
        return 1
    print("\n  ALL CHECKS PASSED — caching layer behaves as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
