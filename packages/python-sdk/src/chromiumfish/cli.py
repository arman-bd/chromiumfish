"""`chromiumfish` command-line interface."""
from __future__ import annotations

import argparse
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

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
