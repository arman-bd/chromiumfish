"""ChromiumFish MCP server — drive the stealth browser from any MCP client.

Exposes ChromiumFish as a `Model Context Protocol <https://modelcontextprotocol.io>`_
server so MCP-speaking agents (Claude Code, Claude Desktop, Cursor, Windsurf, …)
can perceive and operate the hardened browser directly. Tools are driven over the
Chrome DevTools Protocol against a ChromiumFish instance the server launches and
holds for its lifetime — the persona/proxy/timezone you start it with stay active,
so the agent operates a browser that already looks like a real person.

Run it from the CLI::

    chromiumfish mcp --persona-seed alice

…or wire it into an MCP client's config (see the docs). The browser is launched
lazily on the first browser tool call and torn down when the server exits.

Granular tools (``navigate``/``snapshot``/``get_text``/``screenshot``/``click``/
``type_text``/``eval_js``) need no LLM on the server side — the MCP client is the
brain. ``run_task`` additionally delegates a whole plain-language goal to the
fork's *native* in-browser agent, which needs an OpenAI-compatible LLM configured
(``OPENAI_API_*`` / ``--llm-*``).

Requires the ``mcp`` extra: ``pip install "chromiumfish[mcp]"`` (Python ≥3.10).
"""
from __future__ import annotations

import atexit
import base64
import json
import threading
from typing import Any, Optional

from .agent import AgentClient, _CDP, launch_agent


# Builds a readable, selector-addressable list of interactive elements. The raw
# `Page.getAnnotatedPageContent` CDP command returns the AnnotatedPageContent
# *proto* (index-keyed, consumed inside the native agent) — not usable directly
# and not selector-addressable, so we perceive via the DOM instead. Selectors it
# emits are what `click`/`type_text` consume.
_SNAPSHOT_JS = r"""
(function(){
  function sel(el){
    if (el.id) return '#'+CSS.escape(el.id);
    var nm = el.getAttribute('name');
    if (nm) return el.tagName.toLowerCase()+'[name="'+nm+'"]';
    var path=[], e=el;
    while(e && e.nodeType===1 && path.length<4){
      var part=e.tagName.toLowerCase();
      if(e.parentElement){
        var sib=Array.prototype.filter.call(e.parentElement.children,function(c){return c.tagName===e.tagName;});
        if(sib.length>1) part+=':nth-of-type('+(sib.indexOf(e)+1)+')';
      }
      path.unshift(part); e=e.parentElement;
    }
    return path.join(' > ');
  }
  function label(el){
    return (el.getAttribute('aria-label')||el.value||el.placeholder||el.innerText||el.getAttribute('title')||'')
      .trim().replace(/\s+/g,' ').slice(0,80);
  }
  var els=document.querySelectorAll('a,button,input,textarea,select,[role=button],[role=link],[onclick],[contenteditable=true]');
  var out=[], n=0;
  for(var i=0;i<els.length && n<200;i++){
    var el=els[i];
    if(!el.getClientRects().length) continue;
    var role=el.tagName.toLowerCase()+(el.type?'['+el.type+']':'');
    var line='['+n+'] '+role+' "'+label(el)+'"  '+sel(el);
    if(el.href) line+=' -> '+el.href;
    out.push(line); n++;
  }
  return out.length ? out.join('\n') : '(no visible interactive elements)';
})()
"""


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP, Image
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "the MCP server needs the 'mcp' package; install it with "
            '`pip install "chromiumfish[mcp]"` (needs Python ≥3.10).'
        ) from exc
    return FastMCP, Image


# --- lazily-launched browser session, shared across tool calls -------------

_CONFIG: dict[str, Any] = {}
_LOCK = threading.Lock()
_SESSION: Optional[tuple[Any, AgentClient]] = None  # (launch ctx-manager, client)


def _client() -> AgentClient:
    """Return the shared AgentClient, launching the browser on first use."""
    global _SESSION
    with _LOCK:
        if _SESSION is None:
            extra: list[str] = []
            seed = _CONFIG.get("persona_seed")
            if seed:
                extra.append(f"--persona-seed={seed}")
            if _CONFIG.get("headless", True):
                extra.append("--headless=new")
            w, h = _CONFIG.get("window_size", (1920, 1080))
            extra.append(f"--window-size={w},{h}")
            if _CONFIG.get("proxy"):
                extra.append(f"--proxy-server={_CONFIG['proxy']}")
            extra.extend(_CONFIG.get("extra_args") or [])

            cm = launch_agent(
                port=_CONFIG.get("port", 9222),
                chrome=_CONFIG.get("chrome"),
                api_key=_CONFIG.get("api_key", ""),
                api_base=_CONFIG.get("api_base", ""),
                model=_CONFIG.get("model", ""),
                typing=_CONFIG.get("typing", "human"),
                extra_args=extra,
            )
            client = cm.__enter__()
            _SESSION = (cm, client)
            atexit.register(_shutdown)
        return _SESSION[1]


def _shutdown() -> None:
    global _SESSION
    with _LOCK:
        if _SESSION is not None:
            try:
                _SESSION[0].__exit__(None, None, None)
            except Exception:
                pass
            _SESSION = None


class _Page:
    """A short-lived CDP connection to the active page target.

    Reconnecting per call keeps things simple and robust; the page itself
    persists in the browser between calls, so navigation/typed state carries
    over.  Use as a context manager.
    """

    def __init__(self) -> None:
        client = _client()
        self.target_id, ws_url = client._pick_page()
        self.cdp = _CDP(ws_url, client.timeout)

    def __enter__(self) -> "_Page":
        return self

    def __exit__(self, *_exc) -> None:
        self.cdp.close()

    def eval(self, expression: str) -> Any:
        res = self.cdp.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if res.get("exceptionDetails"):
            exc = res["exceptionDetails"]
            raise RuntimeError(exc.get("exception", {}).get("description") or exc.get("text", "eval error"))
        return res.get("result", {}).get("value")


# --- server construction ---------------------------------------------------

def build_server():
    """Build (but don't run) the FastMCP server with all browser tools."""
    FastMCP, Image = _require_mcp()
    mcp = FastMCP("chromiumfish")

    @mcp.tool()
    def navigate(url: str) -> str:
        """Open a URL in the ChromiumFish browser and wait for it to load.

        Returns the resolved URL and page title. Call `snapshot` afterwards to
        see what's on the page.
        """
        with _Page() as p:
            p.cdp.send("Page.enable")
            p.cdp.send("Page.navigate", {"url": url})
            p.cdp.wait_event("Page.loadEventFired", 30)
            title = p.eval("document.title")
            href = p.eval("document.location.href")
        return f"Loaded {href}\nTitle: {title}"

    @mcp.tool()
    def snapshot() -> str:
        """List the page's visible interactive elements, one per line, as
        `[i] <role> "label"  <css-selector>` (links also show `-> url`). Use the
        CSS selector with `click` / `type_text`. For the page's prose use
        `get_text`; for anything else, `eval_js`.
        """
        with _Page() as p:
            return p.eval(_SNAPSHOT_JS) or "(no visible interactive elements)"

    @mcp.tool()
    def get_text() -> str:
        """Return the visible text of the current page (`document.body.innerText`).
        Best for reading articles/long content."""
        with _Page() as p:
            return p.eval("document.body && document.body.innerText || ''") or "(empty)"

    @mcp.tool()
    def screenshot():
        """Capture a PNG screenshot of the current viewport."""
        with _Page() as p:
            res = p.cdp.send("Page.captureScreenshot", {"format": "png"}) or {}
        data = res.get("data", "")
        return Image(data=base64.b64decode(data), format="png")

    @mcp.tool()
    def click(selector: str) -> str:
        """Humanized, trusted click on the first element matching a CSS selector
        (moves the cursor along a bezier path; `navigator.webdriver` stays false).
        Fails if nothing matches."""
        with _Page() as p:
            r = p.cdp.send(
                "Browser.humanizedClickSelector",
                {"targetId": p.target_id, "selector": selector},
            ) or {}
        return f"Clicked {selector!r} at ({r.get('x')}, {r.get('y')})"

    @mcp.tool()
    def type_text(selector: str, text: str, submit: bool = False) -> str:
        """Click the element matching `selector` to focus it, type `text`, and
        optionally press Enter (`submit=True`) to submit a search/form."""
        with _Page() as p:
            p.cdp.send(
                "Browser.humanizedClickSelector",
                {"targetId": p.target_id, "selector": selector},
            )
            p.cdp.send("Input.insertText", {"text": text})
            if submit:
                for kind in ("keyDown", "keyUp"):
                    p.cdp.send(
                        "Input.dispatchKeyEvent",
                        {"type": kind, "key": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13},
                    )
        return f"Typed into {selector!r}" + (" and pressed Enter" if submit else "")

    @mcp.tool()
    def eval_js(expression: str) -> str:
        """Evaluate a JavaScript expression in the page and return its (JSON)
        result. Powerful escape hatch — read anything (`document.querySelectorAll`,
        attributes, computed values) or act on the page."""
        with _Page() as p:
            value = p.eval(expression)
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return str(value)

    @mcp.tool()
    def run_task(task: str, url: str = "") -> str:
        """Delegate a whole plain-language goal to ChromiumFish's *native*
        in-browser agent (perceive → think → act loop, humanized input). Best for
        multi-step flows. Requires an OpenAI-compatible LLM configured on the
        server (`OPENAI_API_*` env or `--llm-*` flags); otherwise use the granular
        tools. Returns the agent's final answer."""
        client = _client()
        result = client.run_task(task, url=url or None)
        if not result.final_text and not result.success:
            return "Task did not complete. (If this needs the native agent, ensure an LLM is configured on the MCP server.)"
        return result.final_text or "(done)"

    return mcp


def run_server(**config: Any) -> None:
    """Configure and run the MCP server over stdio (blocks until the client
    disconnects). Recognized config: ``persona_seed``, ``headless``,
    ``window_size``, ``proxy``, ``port``, ``chrome``, ``typing``, ``api_key``,
    ``api_base``, ``model``, ``extra_args``."""
    _CONFIG.clear()
    _CONFIG.update(config)
    server = build_server()
    try:
        server.run(transport="stdio")
    finally:
        _shutdown()
