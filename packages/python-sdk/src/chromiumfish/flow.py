"""Record/replay cache for native AI agent flows.

A :class:`Flow` is a named, cached, ordered list of resolved steps. The first
run RECORDS it — the in-browser LLM resolves each step and we persist a durable
``{role, name, ordinal}`` descriptor per action. Later runs REPLAY the cached
plan deterministically (descriptor match against the live page, no LLM call);
any step whose target has drifted is HEALED via the LLM and the cache updates
itself. This turns a slow, token-heavy traversal into a fast, near-zero-token
replay — falling back to intelligence only where the page actually changed.

    from chromiumfish.flow import Flow

    checkout = Flow("checkout")                      # cached on disk by name
    r = checkout.run(
        "complete the checkout: fill name 'Test User' and email "
        "'test@example.com', accept terms, place the order",
        url="http://127.0.0.1:8000/checkout",
    )
    print(r.summary())        # e.g. "ok | 7 steps (6 replayed, 1 healed, 0 recorded)"

Caching is ON by default. Pass ``use_cache=False`` (per-run or on the Flow) to
ignore the cache entirely — always run the full LLM loop and neither read nor
overwrite the stored plan.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .agent import AgentClient, AgentResult


def default_flow_dir() -> Path:
    """Where flow plans are cached. Override with ``CHROMIUMFISH_FLOW_DIR``."""
    env = os.environ.get("CHROMIUMFISH_FLOW_DIR")
    return Path(env) if env else Path.home() / ".chromiumfish" / "flows"


class Flow:
    """A named, cacheable agent flow backed by a JSON plan on disk."""

    def __init__(
        self,
        name: str,
        *,
        client: Optional[AgentClient] = None,
        port: int = 9222,
        flow_dir: Optional[os.PathLike | str] = None,
        use_cache: bool = True,
    ):
        self.name = name
        self.client = client or AgentClient(port=port)
        self.dir = Path(flow_dir) if flow_dir is not None else default_flow_dir()
        self.use_cache = use_cache
        self.path = self.dir / f"{name}.json"

    # ----- persistence -----
    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> Optional[list[dict]]:
        """Return the cached step plan, or None if absent/unreadable."""
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text())
        except Exception:
            return None
        if isinstance(data, dict):
            steps = data.get("steps")
            return steps if isinstance(steps, list) else None
        return data if isinstance(data, list) else None

    def save(self, goal: str, steps: list[dict]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"name": self.name, "goal": goal, "steps": steps}, indent=2)
        )

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    # ----- run -----
    def run(
        self,
        goal: str,
        *,
        url: Optional[str] = None,
        max_steps: int = 25,
        model: str = "",
        use_cache: Optional[bool] = None,
        save: bool = True,
    ) -> AgentResult:
        """Run the flow.

        With caching on (default), a stored plan is replayed (and self-healed),
        and the resolved plan is written back. With ``use_cache=False`` the flow
        runs the full LLM loop and the on-disk plan is neither read nor written.
        """
        cache = self.use_cache if use_cache is None else use_cache
        plan = self.load() if cache else None
        result = self.client.run_task(
            goal, url=url, max_steps=max_steps, model=model, plan=plan
        )
        # Persist the resolved steps (the possibly self-healed plan) for replay.
        if cache and save and result.success and result.steps:
            self.save(goal, result.steps)
        return result

    def record(self, goal: str, **kwargs) -> AgentResult:
        """Force a fresh recording: drop any cached plan, then run + save."""
        self.clear()
        return self.run(goal, use_cache=True, **kwargs)

    def replay(self, goal: str, **kwargs) -> AgentResult:
        """Replay the cached plan (healing as needed). Records if none cached."""
        return self.run(goal, use_cache=True, **kwargs)
