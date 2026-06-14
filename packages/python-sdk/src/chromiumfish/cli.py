"""`chromiumfish` command-line interface."""
from __future__ import annotations

import argparse
import json
import shutil
import sys

from .fetch import binary_path, cache_root, fetch, install_dir
from .version import __version__, browser_version


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
