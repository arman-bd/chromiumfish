"""Pinned browser build + release coordinates.

The browser is built privately and published to this repo's GitHub Releases.
`BROWSER_VERSION` is the release tag (without the leading ``v``) the SDK
downloads by default; override it at runtime with ``CHROMIUMFISH_VERSION``.
"""
from __future__ import annotations

import os
import re

_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def assert_safe_version(version: str) -> str:
    """Reject version strings that aren't a plain build tag.

    Versions are interpolated into filesystem cache paths and release URLs, so
    a crafted value like ``../../../etc`` would escape the cache dir (path
    traversal). Real tags are digits, dots, and hyphens (e.g. "150.0.7844",
    "2026.06", "latest")."""
    if version in (".", "..") or not _VERSION_RE.match(version):
        raise ValueError(f"invalid version string: {version!r}")
    return version

# SDK package version. Single source of truth: pyproject.toml reads this via
# [tool.hatch.version] (dynamic = ["version"]).
__version__ = "0.1.4"

# Default ChromiumFish browser build to fetch. Matches src/chrome/VERSION.
DEFAULT_BROWSER_VERSION = "150.0.7844"

# GitHub repo that hosts the release assets (public; binary built from the
# private chromiumfish-browser repo).
RELEASE_REPO = "arman-bd/chromiumfish"

# IP-to-Timezone database, built by packages/geoip/build_ip2tz.py.
# IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0.
#
# Default "latest" auto-tracks the newest monthly build: the SDK reads a small
# pointer (the geoip-latest release manifest) to discover the current concrete
# version, so no SDK republish is needed when a new DB ships. Pin a specific
# version with CHROMIUMFISH_GEOIP_VERSION (e.g. "2026.06") for reproducibility.
DEFAULT_GEOIP_VERSION = "latest"

# Concrete version used when "latest" cannot be resolved (offline + no cached
# pointer). Bump occasionally so the offline floor stays recent.
GEOIP_FALLBACK_VERSION = "2026.06"


def browser_version() -> str:
    """Resolved browser version (env override wins)."""
    return assert_safe_version(
        os.environ.get("CHROMIUMFISH_VERSION", DEFAULT_BROWSER_VERSION)
    )


def release_base_url(version: str | None = None) -> str:
    version = version or browser_version()
    return f"https://github.com/{RELEASE_REPO}/releases/download/v{version}"


def geoip_version() -> str:
    """Configured IP-to-Timezone DB version (env override wins). May be the
    sentinel "latest" — resolve it to a concrete version via ip2tz."""
    return assert_safe_version(
        os.environ.get("CHROMIUMFISH_GEOIP_VERSION", DEFAULT_GEOIP_VERSION)
    )


def geoip_base_url(version: str | None = None) -> str:
    version = version or geoip_version()
    return f"https://github.com/{RELEASE_REPO}/releases/download/geoip-{version}"


def geoip_latest_manifest_url() -> str:
    """Stable URL of the pointer that names the current concrete DB version."""
    return f"https://github.com/{RELEASE_REPO}/releases/download/geoip-latest/latest.json"
