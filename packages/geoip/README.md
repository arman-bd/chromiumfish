# geoip — IP-to-Timezone pipeline

Builds the compact **`ip2tz`** database that the ChromiumFish SDKs use to map an
egress IP to its IANA timezone (so a launched browser's clock matches where its
traffic appears to come from).

> IP Geolocation by <a href='https://db-ip.com'>DB-IP</a>

## What it does

The source — [DB-IP City Lite][dbip] — is a ~130 MB MaxMind-format `.mmdb` with
a full geo record per network (continent / country / city / subdivisions in ten
languages, plus lat/lng) and **no timezone field**. This pipeline:

1. reads every network and resolves its lat/lng centroid to an IANA timezone
   (via `timezonefinder`, cached per unique coordinate);
2. strips everything except the timezone;
3. run-length merges adjacent networks that share a zone;
4. emits a self-describing, **zero-dependency** binary (`ip2tz-<ver>.bin`) plus a
   `.sha256` sidecar.

The ~130 MB input collapses to a ~16 MB artifact with ~1.4M range records that
the SDKs read with a pure-stdlib binary search — no `maxminddb` or
`timezonefinder` at runtime, no per-lookup network call.

## Build

```bash
python3 -m pip install -r requirements.txt   # build-only deps

# download the month's DB-IP City Lite and build:
python3 build_ip2tz.py --download --month 2026-06

# or build from an mmdb already on disk:
python3 build_ip2tz.py --mmdb dbip-city-lite-2026-06.mmdb --out ip2tz-2026.06.bin
```

The source `.mmdb` and the built `ip2tz-*.bin` are **not committed** (see
`.gitignore`) — the `.bin` is published as a GitHub release asset under the
`geoip-<ver>` tag, which the SDKs download and verify against the `.sha256`.

## Releasing a refresh

DB-IP publishes a new City Lite monthly. The
[`Update IP-to-Timezone DB`](../../.github/workflows/geoip.yml) workflow does
this automatically on the 3rd of each month (and via `workflow_dispatch`):

1. builds `ip2tz-<ver>.bin` (`<ver>` = `YYYY.MM`) from that month's City Lite;
2. publishes it (+ `.sha256`) as a `geoip-<ver>` release;
3. updates the stable **`geoip-latest`** release with a `latest.json` pointer
   naming the current version.

The SDKs default to the **`latest`** channel: they read `geoip-latest/latest.json`
at runtime (cached, TTL-gated) to discover the current version, so a new DB is
picked up **without an SDK republish**. Pin a specific version with
`CHROMIUMFISH_GEOIP_VERSION` for reproducibility. The compiled-in
`GEOIP_FALLBACK_VERSION` is only the offline floor; bump it occasionally.

To run a build manually: `python3 build_ip2tz.py --download --month YYYY-MM`.

## Binary format

Big-endian throughout; the readers in
`packages/python-sdk/src/chromiumfish/ip2tz.py` and
`packages/js-sdk/src/ip2tz.ts` must stay in lock-step with the builder.

| field        | type      | notes                                        |
|--------------|-----------|----------------------------------------------|
| magic        | 6 bytes   | `IP2TZ\x01`                                  |
| build_epoch  | uint32    | source mmdb build epoch (provenance)         |
| tz_count     | uint16    | timezone strings (index 0 is always `""`)    |
| v4_count     | uint32    | IPv4 range records                           |
| v6_count     | uint32    | IPv6 range records                           |
| tz_table     | …         | `tz_count` × (uint8 len + utf8 bytes)        |
| v4_block     | …         | `v4_count` × (uint32 start, uint16 tz_idx)   |
| v6_block     | …         | `v6_count` × (16-byte start, uint16 tz_idx)  |

Records are sorted ascending by start and cover the address space contiguously:
record *i* owns `[start_i, start_{i+1} − 1]`. Unmapped space carries `tz_idx 0`
(`""` = unknown). A lookup is therefore "rightmost record whose start ≤ ip" and
always resolves.

## Attribution & license

This database and everything derived from it (the `ip2tz` asset) include
geolocation data from DB-IP, used under [CC BY 4.0][ccby]. The attribution

> IP Geolocation by <a href='https://db-ip.com'>DB-IP</a>

must be preserved wherever the data is used or redistributed.

[dbip]: https://db-ip.com/db/download/ip-to-city-lite
[ccby]: https://creativecommons.org/licenses/by/4.0/
