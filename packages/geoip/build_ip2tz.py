#!/usr/bin/env python3
"""Cleanup pipeline: DB-IP City Lite mmdb  ->  compact IP-to-Timezone DB.

IP Geolocation by DB-IP (https://db-ip.com). DB-IP City Lite is distributed
under CC BY 4.0, which requires this attribution to be preserved wherever the
data (or anything derived from it, including the ip2tz asset this pipeline
produces) is used. See README.md.

The free DB-IP City Lite database is ~130 MB and carries a full geo record per
network (continent / country / city / subdivisions in ten languages, plus
lat/lng). It does NOT carry a timezone field. This pipeline strips all of that
away and produces a single artifact that answers exactly one question:

    given an IP address, which IANA timezone is it in?

Timezone is derived from the network's lat/lng centroid via `timezonefinder`
(cached per unique coordinate, so the polygon lookup runs a few thousand times,
not millions). Adjacent networks that resolve to the same zone are run-length
merged, which collapses the millions of mmdb networks down to a small table.

Output: a self-describing, zero-dependency binary (see FORMAT below) plus a
`.sha256` sidecar. This is the release asset the SDKs download and read with a
pure-stdlib binary search — no maxminddb / timezonefinder needed at runtime.

Usage:
    # download the month's DB-IP City Lite and build:
    python3 build_ip2tz.py --download --month 2026-06

    # build from an mmdb already on disk:
    python3 build_ip2tz.py --mmdb dbip-city-lite-2026-06.mmdb --out ip2tz-2026.06.bin

Build-only dependencies (NOT shipped to clients): maxminddb, timezonefinder.
    python3 -m pip install maxminddb timezonefinder

FORMAT (ip2tz binary, big-endian throughout) — kept in sync with the readers
in packages/python-sdk/.../ip2tz.py and packages/js-sdk/src/ip2tz.ts:

    magic        6 bytes   b"IP2TZ\\x01"
    build_epoch  uint32    mmdb build epoch (provenance)
    tz_count     uint16    number of timezone strings (entry 0 is always "")
    v4_count     uint32    number of IPv4 range records
    v6_count     uint32    number of IPv6 range records
    tz_table     tz_count * (uint8 len + utf8 bytes)
    v4_block     v4_count * (uint32 start, uint16 tz_idx)      # 6 bytes each
    v6_block     v6_count * (16-byte start, uint16 tz_idx)     # 18 bytes each

Range records are sorted ascending by start and cover the address space
contiguously: record i owns [start_i, start_{i+1} - 1]; the last record owns
everything up to the family max. Unmapped space carries tz_idx 0 ("" = unknown).
A lookup is therefore "rightmost record whose start <= ip" and always resolves.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import ipaddress
import shutil
import struct
import sys
import time
import urllib.request
from pathlib import Path

MAGIC = b"IP2TZ\x01"
DBIP_URL = "https://download.db-ip.com/free/dbip-city-lite-{month}.mmdb.gz"

V4_MAX = (1 << 32) - 1
V6_MAX = (1 << 128) - 1


def log(msg: str) -> None:
    print(f"[ip2tz-build] {msg}", file=sys.stderr)


def download_dbip(month: str, dest_dir: Path) -> Path:
    """Fetch + gunzip the month's DB-IP City Lite mmdb. month is 'YYYY-MM'."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    gz = dest_dir / f"dbip-city-lite-{month}.mmdb.gz"
    mmdb = dest_dir / f"dbip-city-lite-{month}.mmdb"
    if mmdb.exists():
        log(f"reusing existing {mmdb.name}")
        return mmdb
    url = DBIP_URL.format(month=month)
    if not gz.exists():
        log(f"downloading {url}")
        with urllib.request.urlopen(url) as r, open(gz, "wb") as f:  # noqa: S310
            shutil.copyfileobj(r, f)
    log(f"decompressing {gz.name}")
    with gzip.open(gz, "rb") as src, open(mmdb, "wb") as out:
        shutil.copyfileobj(src, out)
    return mmdb


def collect_ranges(mmdb_path: Path):
    """Walk the mmdb, resolve each network's centroid to an IANA timezone, and
    return (v4_ranges, v6_ranges, build_epoch) where each *_ranges is a list of
    (start_int, end_int_inclusive, tz_name) sorted ascending by start.

    tz_name is "" when the network has no usable coordinates."""
    import maxminddb
    from timezonefinder import TimezoneFinder

    tf = TimezoneFinder()
    reader = maxminddb.open_database(str(mmdb_path))
    build_epoch = int(reader.metadata().build_epoch)

    coord_cache: dict[tuple, str] = {}
    v4: list[tuple[int, int, str]] = []
    v6: list[tuple[int, int, str]] = []

    n = 0
    t0 = time.time()
    for net, rec in reader:
        n += 1
        if n % 500_000 == 0:
            log(f"  scanned {n:,} networks ({len(coord_cache):,} unique coords, "
                f"{time.time() - t0:.0f}s)")
        tz = ""
        loc = (rec or {}).get("location") if rec else None
        if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
            key = (round(loc["latitude"], 4), round(loc["longitude"], 4))
            tz = coord_cache.get(key)
            if tz is None:
                tz = tf.timezone_at(lat=loc["latitude"], lng=loc["longitude"]) or ""
                coord_cache[key] = tz

        start = int(net.network_address)
        end = int(net.broadcast_address)
        if isinstance(net, ipaddress.IPv4Network):
            v4.append((start, end, tz))
        else:
            v6.append((start, end, tz))

    reader.close()
    v4.sort(key=lambda r: r[0])
    v6.sort(key=lambda r: r[0])
    log(f"scanned {n:,} networks total; {len(coord_cache):,} unique coordinates; "
        f"v4={len(v4):,} v6={len(v6):,}")
    return v4, v6, build_epoch


def to_transitions(ranges: list[tuple[int, int, str]], fam_max: int) -> list[tuple[int, str]]:
    """Turn (start, end, tz) ranges into contiguous, run-length-merged
    (start, tz) transitions covering [0, fam_max]. Gaps become "" (unknown)."""
    out: list[tuple[int, str]] = []
    cursor = 0  # next address that needs covering

    def push(start: int, tz: str) -> None:
        if out and out[-1][1] == tz:
            return  # same zone as previous run -> extend it, emit nothing
        out.append((start, tz))

    for start, end, tz in ranges:
        if start > cursor:
            push(cursor, "")          # gap before this network -> unknown
        push(start, tz)
        cursor = max(cursor, end + 1)
    if cursor <= fam_max:
        push(cursor, "")              # trailing unmapped space
    if not out or out[0][0] != 0:
        out.insert(0, (0, ""))        # guarantee coverage from address 0
    return out


def build_blob(v4_tr, v6_tr, build_epoch: int) -> bytes:
    # Shared timezone string table; index 0 is always "" (unknown).
    tz_list: list[str] = [""]
    tz_index: dict[str, int] = {"": 0}

    def idx(tz: str) -> int:
        i = tz_index.get(tz)
        if i is None:
            i = len(tz_list)
            tz_index[tz] = i
            tz_list.append(tz)
        return i

    v4_records = [(start, idx(tz)) for start, tz in v4_tr]
    v6_records = [(start, idx(tz)) for start, tz in v6_tr]

    if len(tz_list) > 0xFFFF:
        raise SystemExit("too many timezones for a uint16 index")

    parts: list[bytes] = []
    parts.append(MAGIC)
    parts.append(struct.pack(">I", build_epoch))
    parts.append(struct.pack(">H", len(tz_list)))
    parts.append(struct.pack(">I", len(v4_records)))
    parts.append(struct.pack(">I", len(v6_records)))
    for tz in tz_list:
        b = tz.encode("utf-8")
        if len(b) > 0xFF:
            raise SystemExit(f"timezone name too long: {tz}")
        parts.append(struct.pack(">B", len(b)))
        parts.append(b)
    for start, ti in v4_records:
        parts.append(struct.pack(">IH", start, ti))
    for start, ti in v6_records:
        parts.append(start.to_bytes(16, "big"))
        parts.append(struct.pack(">H", ti))

    log(f"{len(tz_list)} timezones; v4 records {len(v4_records):,}; "
        f"v6 records {len(v6_records):,}")
    return b"".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mmdb", type=Path, help="path to a DB-IP City Lite mmdb")
    ap.add_argument("--download", action="store_true",
                    help="download the month's DB-IP City Lite first")
    ap.add_argument("--month", default="2026-06",
                    help="DB-IP month tag 'YYYY-MM' (with --download)")
    ap.add_argument("--out", type=Path,
                    help="output path (default ip2tz-<YYYY.MM>.bin next to script)")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    if args.download:
        mmdb = download_dbip(args.month, here)
    elif args.mmdb:
        mmdb = args.mmdb
    else:
        ap.error("pass --download (with --month) or --mmdb")

    out = args.out or here / f"ip2tz-{args.month.replace('-', '.')}.bin"

    v4, v6, build_epoch = collect_ranges(mmdb)
    v4_tr = to_transitions(v4, V4_MAX)
    v6_tr = to_transitions(v6, V6_MAX)
    blob = build_blob(v4_tr, v6_tr, build_epoch)

    out.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    (out.with_name(out.name + ".sha256")).write_text(f"{digest}  {out.name}\n")
    log(f"wrote {out} ({len(blob) / 1_048_576:.2f} MiB)")
    log(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
