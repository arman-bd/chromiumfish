"""Pinned browser build + release coordinates.

The browser is built privately and published to this repo's GitHub Releases.
`BROWSER_VERSION` is the release tag (without the leading ``v``) the SDK
downloads by default; override it at runtime with ``CHROMIUMFISH_VERSION``.
"""
from __future__ import annotations

import os

# SDK package version. Single source of truth: pyproject.toml reads this via
# [tool.hatch.version] (dynamic = ["version"]).
__version__ = "0.1.0"

# Default ChromiumFish browser build to fetch. Matches src/chrome/VERSION.
DEFAULT_BROWSER_VERSION = "150.0.7844"

# GitHub repo that hosts the release assets (public; binary built from the
# private chromiumfish-browser repo).
RELEASE_REPO = "arman-bd/chromiumfish"


def browser_version() -> str:
    """Resolved browser version (env override wins)."""
    return os.environ.get("CHROMIUMFISH_VERSION", DEFAULT_BROWSER_VERSION)


def release_base_url(version: str | None = None) -> str:
    version = version or browser_version()
    return f"https://github.com/{RELEASE_REPO}/releases/download/v{version}"
