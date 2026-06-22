"""`chromiumfish` command-line interface."""
from __future__ import annotations

import argparse
import json
import shutil
import sys

from .fetch import binary_path, cache_root, fetch, install_dir
from .version import __version__, browser_version


def _serve(args) -> int:
    """Launch ChromiumFish as a bare CDP endpoint for external agents.

    Uses ``subprocess.Popen`` (not Playwright) deliberately: we're exposing the
    DevTools endpoint for a third-party client to attach to, so we just launch
    the binary directly. Reuses ``build_args`` for the persona/window flags and
    ``resolve_timezone`` for the ``--timezone``/``auto`` handling, then blocks
    until interrupted and tears the temp profile down on exit.
    """
    import os
    import signal
    import subprocess
    import tempfile
    import time
    import urllib.request

    from .fetch import binary_path
    from .launcher import build_args, resolve_timezone

    try:
        w, h = (int(x) for x in args.window_size.lower().split("x", 1))
    except Exception:
        print(f"invalid --window-size {args.window_size!r}; expected WIDTHxHEIGHT, e.g. 1920x1080",
              file=sys.stderr)
        return 1

    exe = binary_path(args.browser_version)  # fetches if not cached
    profile = tempfile.mkdtemp(prefix="cf-serve-")

    extra: list[str] = []
    if args.headless:
        extra.append("--headless=new")
    if args.proxy:
        extra.append(f"--proxy-server={args.proxy}")
    if args.extra_args:
        extra.extend(a for a in args.extra_args.split(",") if a)

    cmd = [
        str(exe),
        f"--remote-debugging-port={args.port}",
        # External clients send an Origin header DevTools rejects unless allowed;
        # the SDK's own raw-CDP client sidesteps this with suppress_origin, but a
        # third-party client (Hermes/OpenClaw/...) needs the server-side allow.
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        *build_args(persona_seed=args.persona_seed, window_size=(w, h), extra_args=extra),
    ]

    env = dict(os.environ)
    tz = resolve_timezone(
        args.timezone,
        proxy={"server": args.proxy} if args.proxy else None,
        download=True,
    )
    if tz:
        env["TZ"] = tz

    base = f"http://127.0.0.1:{args.port}"
    # start_new_session: put the browser in its own process group so we can
    # signal the WHOLE tree (browser + GPU/renderer/network helpers) on exit —
    # a bare terminate() on the main process leaks the helpers. DEVNULL keeps
    # the browser's chatter out of our stdout.
    proc = subprocess.Popen(
        cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    def _teardown() -> None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(proc.pid), sig)
            except ProcessLookupError:
                break  # already gone
            except Exception:
                proc.kill()
                break
            try:
                proc.wait(timeout=8)
                break
            except Exception:
                continue  # didn't die on SIGTERM — escalate to SIGKILL
        shutil.rmtree(profile, ignore_errors=True)

    # Own both signals explicitly so teardown runs no matter how we're stopped:
    # Ctrl-C (SIGINT), a process manager's SIGTERM, and even the SIG_IGN that a
    # shell hands a backgrounded job (which Python would otherwise preserve).
    def _raise_interrupt(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGINT, _raise_interrupt)
    signal.signal(signal.SIGTERM, _raise_interrupt)

    try:
        deadline = time.time() + args.timeout
        ver = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{base}/json/version", timeout=1) as r:
                    ver = json.load(r)
                break
            except Exception:
                if proc.poll() is not None:
                    print("ChromiumFish exited before the CDP endpoint came up", file=sys.stderr)
                    _teardown()
                    return 1
                time.sleep(0.4)
        if ver is None:
            print("ChromiumFish did not expose its CDP endpoint in time", file=sys.stderr)
            _teardown()
            return 1

        ws = ver.get("webSocketDebuggerUrl", "")
        print(f"ChromiumFish {ver.get('Browser', '')} ready — CDP endpoint for external agents", flush=True)
        print(f"  HTTP : {base}   (discovery: {base}/json/version)", flush=True)
        if ws:
            print(f"  WS   : {ws}", flush=True)
        print(flush=True)
        print("Attach an agent, e.g.:", flush=True)
        print(f'  Hermes       ~/.hermes/config.yaml  ->  browser: {{ cdp_url: "{base}" }}', flush=True)
        print(f'  browser-use  BrowserSession(cdp_url="{base}")', flush=True)
        print(f'  OpenClaw     profile  cdpUrl: "{base}"', flush=True)
        print("Ctrl-C to stop.", flush=True)
        proc.wait()
    except KeyboardInterrupt:
        print("\nstopping…", flush=True)
    finally:
        _teardown()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chromiumfish",
        description="Fetch and manage the ChromiumFish browser build.",
    )
    parser.add_argument("-V", "--version", action="version",
                        version=f"chromiumfish {__version__} (browser {browser_version()})")
    sub = parser.add_subparsers(dest="cmd")

    f = sub.add_parser("fetch", help="download + cache the browser build")
    f.add_argument("--browser-version", default=None, help="override the build version")
    f.add_argument("--force", action="store_true", help="re-download even if cached")

    sub.add_parser("path", help="print the cached binary path (fetching if missing)")
    sub.add_parser("clear", help="remove all cached browser builds")

    # Launch a plain CDP endpoint for external agent frameworks (Hermes,
    # OpenClaw, browser-use, ...) to attach to. Unlike `launch_agent`, this adds
    # NO `--agent-*` switches — it just exposes Chrome DevTools Protocol with the
    # persona/proxy/timezone you choose, so any CDP client drives the browser.
    sv = sub.add_parser(
        "serve",
        help="launch a CDP endpoint for external agents (Hermes, OpenClaw, browser-use)",
    )
    sv.add_argument("--port", type=int, default=9222, help="remote-debugging port (default 9222)")
    sv.add_argument("--persona-seed", default=None, help="stable fingerprint persona seed")
    sv.add_argument("--proxy", default=None, help="proxy URL: scheme://[user:pass@]host:port")
    sv.add_argument("--window-size", default="1920x1080", help="WIDTHxHEIGHT (default 1920x1080)")
    sv.add_argument("--timezone", default=None, help='IANA zone, or "auto" to derive from the egress IP')
    sv.add_argument("--headless", action="store_true", help="run headless (default: headed)")
    sv.add_argument("--browser-version", default=None, help="override the build version")
    sv.add_argument("--extra-args", default=None, help="comma-separated extra Chromium flags")
    sv.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for the endpoint")

    # Run an MCP server exposing the browser to MCP clients (Claude, Cursor, ...).
    mc = sub.add_parser(
        "mcp",
        help="run an MCP server exposing the browser to MCP clients (Claude, Cursor, ...)",
    )
    mc.add_argument("--persona-seed", default=None, help="stable fingerprint persona seed")
    mc.add_argument("--headed", action="store_true", help="show the browser window (default: headless)")
    mc.add_argument("--window-size", default="1920x1080", help="WIDTHxHEIGHT (default 1920x1080)")
    mc.add_argument("--proxy", default=None, help="proxy URL: scheme://[user:pass@]host:port")
    mc.add_argument("--port", type=int, default=9222, help="CDP port the server drives (default 9222)")
    mc.add_argument("--typing", default="human", help="agent typing speed: human|fast|instant")
    mc.add_argument("--llm-key", default=None, help="OpenAI-compatible key for run_task (else OPENAI_API_KEY)")
    mc.add_argument("--llm-base", default=None, help="LLM base URL for run_task (else OPENAI_API_BASE)")
    mc.add_argument("--llm-model", default=None, help="LLM model for run_task (else OPENAI_API_MODEL)")

    # AI agent flow record/replay cache (talks to a running ChromiumFish CDP).
    flow_p = sub.add_parser("flow", help="record/replay cached AI agent flows")
    flow_sub = flow_p.add_subparsers(dest="flow_cmd")
    fr = flow_sub.add_parser("run", help="run a flow (replay if cached, else record)")
    fr.add_argument("name", help="flow name (cache key)")
    fr.add_argument("--goal", required=True, help="natural-language task goal")
    fr.add_argument("--url", default=None, help="page to start on")
    fr.add_argument("--port", type=int, default=9222, help="CDP port")
    fr.add_argument("--model", default="", help="override the agent model")
    fr.add_argument("--max-steps", type=int, default=25)
    fr.add_argument("--no-cache", action="store_true",
                    help="ignore the cache: always run the full LLM loop")
    fs = flow_sub.add_parser("show", help="print a cached flow plan")
    fs.add_argument("name")
    fc = flow_sub.add_parser("clear", help="delete a cached flow plan")
    fc.add_argument("name")
    flow_sub.add_parser("list", help="list cached flows")

    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        path = fetch(args.browser_version, force=args.force)
        print(path)
        return 0
    if args.cmd == "path":
        print(binary_path())
        return 0
    if args.cmd == "clear":
        root = cache_root()
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
            print(f"removed {root}")
        else:
            print("nothing to remove")
        return 0
    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "mcp":
        try:
            w, h = (int(x) for x in args.window_size.lower().split("x", 1))
        except Exception:
            print(f"invalid --window-size {args.window_size!r}; expected WIDTHxHEIGHT, e.g. 1920x1080",
                  file=sys.stderr)
            return 1
        from .mcp import run_server
        run_server(
            persona_seed=args.persona_seed,
            headless=not args.headed,
            window_size=(w, h),
            proxy=args.proxy,
            port=args.port,
            typing=args.typing,
            api_key=args.llm_key or "",
            api_base=args.llm_base or "",
            model=args.llm_model or "",
        )
        return 0
    if args.cmd == "flow":
        from .flow import Flow, default_flow_dir
        if args.flow_cmd == "run":
            flow = Flow(args.name, port=args.port)
            res = flow.run(args.goal, url=args.url, max_steps=args.max_steps,
                           model=args.model, use_cache=not args.no_cache)
            print(res.summary())
            print(res.final_text)
            return 0 if res.success else 2
        if args.flow_cmd == "show":
            steps = Flow(args.name).load()
            print(json.dumps(steps, indent=2) if steps is not None
                  else f"no cached flow '{args.name}'")
            return 0
        if args.flow_cmd == "clear":
            Flow(args.name).clear()
            print(f"cleared flow '{args.name}'")
            return 0
        if args.flow_cmd == "list":
            d = default_flow_dir()
            names = sorted(p.stem for p in d.glob("*.json")) if d.exists() else []
            print("\n".join(names) if names else f"no flows in {d}")
            return 0
        flow_p.print_help()
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
