"""ChromiumFish — a stealth Chromium build with a Playwright harness.

Quick start (sync)::

    from chromiumfish.sync_api import Chromiumfish

    with Chromiumfish(persona_seed=27182) as browser:
        page = browser.new_page()
        page.goto("https://example.com")

Quick start (async)::

    from chromiumfish.async_api import AsyncChromiumfish

    async with AsyncChromiumfish(persona_seed=27182) as browser:
        page = await browser.new_page()
"""
from __future__ import annotations

from .fetch import binary_path, fetch, install_dir
from .ip2tz import fetch_db, lookup_timezone, resolve_timezone, resolve_version
from .version import (
    DEFAULT_BROWSER_VERSION,
    DEFAULT_GEOIP_VERSION,
    __version__,
    browser_version,
    geoip_version,
)

__all__ = [
    "__version__",
    "DEFAULT_BROWSER_VERSION",
    "DEFAULT_GEOIP_VERSION",
    "browser_version",
    "geoip_version",
    "fetch",
    "binary_path",
    "install_dir",
    "fetch_db",
    "lookup_timezone",
    "resolve_timezone",
    "resolve_version",
]
