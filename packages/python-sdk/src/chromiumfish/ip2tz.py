"""IP-to-Timezone lookup backed by the downloadable ``ip2tz`` release asset.

IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0.

The asset is built offline by ``packages/geoip/build_ip2tz.py`` from DB-IP City
Lite and published to GitHub Releases. At runtime this module downloads it once
(SHA-256 verified, cached next to the browser build), then answers IP -> IANA
timezone with a pure-stdlib binary search — no maxminddb / timezonefinder, no
per-call network round trip.

    from chromiumfish.ip2tz import resolve_timezone, lookup_timezone

    lookup_timezone("8.8.8.8")          # -> "America/Los_Angeles"
    resolve_timezone()                  # probe own egress IP -> its timezone
    resolve_timezone(proxy="http://user:pass@host:port")

Binary format is documented in build_ip2tz.py; the two must stay in lock-step.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .fetch import cache_root
from .version import (
    GEOIP_FALLBACK_VERSION,
    assert_safe_version,
    geoip_base_url,
    geoip_latest_manifest_url,
    geoip_version,
)

MAGIC = b"IP2TZ\x01"
_V4_REC = 6   # uint32 start + uint16 tz_idx
_V6_REC = 18  # 16-byte start + uint16 tz_idx

_EGRESS_PROBE = "https://ipinfo.io/json"

_LATEST = "latest"
# How long a resolved "latest" pointer is trusted before re-checking the
# manifest. Override with CHROMIUMFISH_GEOIP_TTL (seconds).
_LATEST_TTL = int(os.environ.get("CHROMIUMFISH_GEOIP_TTL", 7 * 24 * 3600))


def _geoip_dir() -> Path:
    return cache_root() / "geoip"


def _pointer_path() -> Path:
    return _geoip_dir() / "latest.json"


def resolve_version(version: str | None = None, *, download: bool = True) -> str:
    """Turn a configured version (possibly the "latest" sentinel) into a
    concrete version like "2026.06".

    For "latest": use a cached pointer while it is fresh (< TTL); otherwise
    fetch the geoip-latest manifest. Falls back to a stale pointer, then to the
    compiled-in floor, so resolution never hard-fails offline."""
    version = version or geoip_version()
    if version != _LATEST:
        return version

    ptr = _pointer_path()
    cached: dict | None = None
    if ptr.exists():
        try:
            cached = json.loads(ptr.read_text())
        except (OSError, json.JSONDecodeError):
            cached = None
        if cached and cached.get("version") and (
            time.time() - ptr.stat().st_mtime < _LATEST_TTL
        ):
            return cached["version"]

    if download:
        try:
            req = urllib.request.Request(
                geoip_latest_manifest_url(),
                headers={"User-Agent": "chromiumfish"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310
                manifest = json.load(r)
            ver = manifest.get("version")
            if ver:
                ptr.parent.mkdir(parents=True, exist_ok=True)
                ptr.write_text(json.dumps(manifest))
                return ver
        except Exception as e:  # noqa: BLE001 - resolution is best-effort
            print(f"[chromiumfish] could not resolve latest ip2tz version: {e}",
                  file=sys.stderr)

    if cached and cached.get("version"):
        return cached["version"]
    return GEOIP_FALLBACK_VERSION


def asset_name(version: str | None = None) -> str:
    return f"ip2tz-{assert_safe_version(resolve_version(version))}.bin"


def db_path(version: str | None = None) -> Path:
    return _geoip_dir() / f"ip2tz-{assert_safe_version(resolve_version(version))}.bin"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def fetch_db(version: str | None = None, *, force: bool = False) -> Path:
    """Ensure the ip2tz DB is cached locally and return its path. Resolves the
    "latest" sentinel to a concrete version once, up front."""
    version = assert_safe_version(resolve_version(version))  # concrete, e.g. "2026.06"
    dest = _geoip_dir() / f"ip2tz-{version}.bin"
    if dest.exists() and not force:
        return dest

    asset = f"ip2tz-{version}.bin"
    base = geoip_base_url(version)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{base}/{asset}"
    print(f"[chromiumfish] downloading {url}", file=sys.stderr)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as out:  # noqa: S310
            while chunk := r.read(1 << 20):
                out.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    try:
        with urllib.request.urlopen(f"{url}.sha256", timeout=30) as r:  # noqa: S310
            expected = r.read().decode().split()[0].strip()
        actual = _sha256(tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"ip2tz checksum mismatch: {actual} != {expected}")
    except urllib.error.URLError:
        print("[chromiumfish] warning: no ip2tz .sha256 published, skipping verify",
              file=sys.stderr)

    tmp.replace(dest)
    return dest


class Ip2TzDB:
    """In-memory reader over an ip2tz blob. Lookups are O(log n) binary
    searches directly over the raw record bytes (big-endian fixed-width keys
    compare byte-wise the same as numerically, so no per-record decode)."""

    def __init__(self, blob: bytes) -> None:
        if blob[:len(MAGIC)] != MAGIC:
            raise ValueError("not an ip2tz database (bad magic)")
        self.build_epoch = struct.unpack_from(">I", blob, 6)[0]
        tz_count = struct.unpack_from(">H", blob, 10)[0]
        self.v4_count = struct.unpack_from(">I", blob, 12)[0]
        self.v6_count = struct.unpack_from(">I", blob, 16)[0]

        off = 20
        tzs: list[str] = []
        for _ in range(tz_count):
            ln = blob[off]
            off += 1
            tzs.append(blob[off:off + ln].decode("utf-8"))
            off += ln
        self._tz = tzs

        self._v4 = memoryview(blob)[off:off + self.v4_count * _V4_REC]
        off += self.v4_count * _V4_REC
        self._v6 = memoryview(blob)[off:off + self.v6_count * _V6_REC]
        # Keep a reference so the backing buffer outlives the memoryviews.
        self._blob = blob

    @classmethod
    def load(cls, path: Path | str) -> "Ip2TzDB":
        return cls(Path(path).read_bytes())

    @staticmethod
    def _rightmost(block: memoryview, count: int, rec: int, keylen: int,
                   key: bytes) -> int:
        """Index of the rightmost record whose start <= key, or -1."""
        lo, hi = 0, count
        while lo < hi:
            mid = (lo + hi) // 2
            base = mid * rec
            if bytes(block[base:base + keylen]) <= key:
                lo = mid + 1
            else:
                hi = mid
        return lo - 1

    def lookup(self, ip: str) -> str | None:
        """Return the IANA timezone for ``ip``, or None if unmapped."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if isinstance(addr, ipaddress.IPv6Address):
            mapped = addr.ipv4_mapped
            if mapped is not None:
                addr = mapped

        if isinstance(addr, ipaddress.IPv4Address):
            key = int(addr).to_bytes(4, "big")
            i = self._rightmost(self._v4, self.v4_count, _V4_REC, 4, key)
            block, rec, keylen = self._v4, _V4_REC, 4
        else:
            key = int(addr).to_bytes(16, "big")
            i = self._rightmost(self._v6, self.v6_count, _V6_REC, 16, key)
            block, rec, keylen = self._v6, _V6_REC, 16

        if i < 0:
            return None
        ti = struct.unpack_from(">H", block, i * rec + keylen)[0]
        tz = self._tz[ti]
        return tz or None


_DB_LOCK = threading.Lock()
# Keyed by *resolved* concrete version so a later lookup with a different
# version doesn't silently reuse the first DB loaded.
_DB_CACHE: dict[str, Ip2TzDB] = {}


def _get_db(version: str | None = None, *, download: bool = True) -> Ip2TzDB:
    with _DB_LOCK:
        resolved = assert_safe_version(resolve_version(version, download=download))
        db = _DB_CACHE.get(resolved)
        if db is None:
            path = _geoip_dir() / f"ip2tz-{resolved}.bin"
            if not path.exists():
                if not download:
                    raise FileNotFoundError(
                        "ip2tz DB not installed. Call chromiumfish.ip2tz.fetch_db()."
                    )
                path = fetch_db(resolved)
            db = Ip2TzDB.load(path)
            _DB_CACHE[resolved] = db
        return db


def lookup_timezone(ip: str, *, version: str | None = None,
                    download: bool = True) -> str | None:
    """IANA timezone for an IP address, downloading the DB on first use."""
    return _get_db(version, download=download).lookup(ip)


def egress_ip(proxy: str | None = None, *, timeout: float = 8.0) -> str | None:
    """Best-effort lookup of the egress IP (through ``proxy`` if given)."""
    handlers: list = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(_EGRESS_PROBE, headers={"User-Agent": "chromiumfish"})
    try:
        with opener.open(req, timeout=timeout) as r:
            return (json.load(r) or {}).get("ip")
    except Exception as e:  # noqa: BLE001 - probe is best-effort
        print(f"[chromiumfish] egress probe failed: {e}", file=sys.stderr)
        return None


def resolve_timezone(*, ip: str | None = None, proxy: str | None = None,
                     version: str | None = None,
                     download: bool = True) -> str | None:
    """Resolve a timezone from an IP. When ``ip`` is omitted, probe the egress
    IP first (honoring ``proxy``). Returns None if nothing resolves."""
    if ip is None:
        ip = egress_ip(proxy)
        if not ip:
            return None
    return lookup_timezone(ip, version=version, download=download)
