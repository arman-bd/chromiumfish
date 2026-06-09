"""FingerprintJS-shaped canvas probe at max throughput.

Each "probe" replays the *exact* op stream FingerprintJS issues in its
canvas fingerprint module: a 240×60 text probe (two fillTexts + a
rectangle background) plus a 122×110 geometry probe (three multiplied
arcs + an even-odd ring), then `getImageData` on both. That's ~25 ops
+ 2 readbacks per probe.

Reference: https://github.com/fingerprintjs/fingerprintjs/blob/master/src/sources/canvas.ts

Usage:
    pip install msgpack websockets
    python3 fp_bench.py                       # default: 1024 concurrent sessions, 50 probes each
    python3 fp_bench.py --sessions 4096 --probes 20
"""

import argparse
import asyncio
import base64
import math
import statistics
import time

import msgpack
import websockets


def b64_basic(creds: str) -> str:
    return base64.b64encode(creds.encode()).decode()


# ----- The fpjs canvas probe op stream -----------------------------------

TEXT_W, TEXT_H = 240, 60
GEOM_W, GEOM_H = 122, 110
FP_TEXT = "Cwm fjordbank glyphs vext quiz, \U0001F603"


def text_canvas_ops():
    return [
        {"op": "SetTextBaseline", "args": "top"},
        {"op": "SetFont", "args": "14px Arial"},
        {"op": "SetTextBaseline", "args": "alphabetic"},
        {"op": "SetFillStyle", "args": {"k": "Color", "v": "#f60"}},
        {"op": "FillRect", "args": {"x": 125.0, "y": 1.0, "w": 62.0, "h": 20.0}},
        {"op": "SetFillStyle", "args": {"k": "Color", "v": "#069"}},
        {"op": "FillText", "args": {"text": FP_TEXT, "x": 2.0, "y": 15.0, "max_width": None}},
        {"op": "SetFillStyle", "args": {"k": "Color", "v": "rgba(102, 204, 0, 0.7)"}},
        {"op": "FillText", "args": {"text": FP_TEXT, "x": 4.0, "y": 17.0, "max_width": None}},
    ]


def geom_canvas_ops():
    ops = [
        {"op": "SetGlobalCompositeOperation", "args": "multiply"},
    ]
    for color, x, y in [("#f2f", 40, 40), ("#2ff", 80, 40), ("#ff2", 60, 80)]:
        ops += [
            {"op": "SetFillStyle", "args": {"k": "Color", "v": color}},
            {"op": "BeginPath"},
            {"op": "Arc", "args": {
                "x": float(x), "y": float(y), "r": 40.0,
                "start": 0.0, "end": math.pi * 2, "counter_clockwise": True,
            }},
            {"op": "ClosePath"},
            {"op": "Fill"},
        ]
    ops += [
        {"op": "SetFillStyle", "args": {"k": "Color", "v": "#f9c"}},
        {"op": "Arc", "args": {
            "x": 60.0, "y": 60.0, "r": 60.0,
            "start": 0.0, "end": math.pi * 2, "counter_clockwise": True,
        }},
        {"op": "Arc", "args": {
            "x": 60.0, "y": 60.0, "r": 20.0,
            "start": 0.0, "end": math.pi * 2, "counter_clockwise": True,
        }},
        {"op": "Fill"},
    ]
    return ops


async def one_probe(send, recv, canvas_id_base):
    """Issue one full fpjs canvas probe; returns (op_count, bytes_pulled)."""
    text_id = canvas_id_base
    geom_id = canvas_id_base + 1
    ops_run = 0

    # text canvas
    await send({"t": "CreateCanvas2D", "v": {
        "id": text_id, "width": TEXT_W, "height": TEXT_H, "opaque": True,
    }})
    text_ops = text_canvas_ops()
    await send({"t": "Canvas2DBatch", "v": {"id": text_id, "ops": text_ops}})
    ops_run += len(text_ops)

    # geometry canvas
    await send({"t": "CreateCanvas2D", "v": {
        "id": geom_id, "width": GEOM_W, "height": GEOM_H, "opaque": True,
    }})
    geom_ops = geom_canvas_ops()
    await send({"t": "Canvas2DBatch", "v": {"id": geom_id, "ops": geom_ops}})
    ops_run += len(geom_ops)

    # readbacks
    await send({"t": "GetCanvas2DImageData", "v": {
        "id": text_id, "x": 0, "y": 0, "w": TEXT_W, "h": TEXT_H,
    }})
    await send({"t": "GetCanvas2DImageData", "v": {
        "id": geom_id, "x": 0, "y": 0, "w": GEOM_W, "h": GEOM_H,
    }})

    r1 = await recv()
    r2 = await recv()
    bytes_pulled = 0
    for r in (r1, r2):
        if r.get("t") == "ImageData":
            bytes_pulled += len(r["v"]["pixels"])
        else:
            # Surface non-fatal errors (e.g. UnsupportedOp for some path
            # variant) but keep going; bench is throughput-oriented.
            pass

    # cleanup so the session-side HashMap doesn't grow unbounded
    await send({"t": "DestroyCanvas", "v": {"id": text_id}})
    await send({"t": "DestroyCanvas", "v": {"id": geom_id}})
    return ops_run, bytes_pulled


async def session_worker(url, creds, sid, probes, latencies_ms, counters):
    headers = {"Authorization": f"Basic {b64_basic(creds)}"}
    async with websockets.connect(
        url, additional_headers=headers, max_size=2**24,
        ping_interval=None,  # tolerate long queue-stalled sessions over WAN
        open_timeout=60, close_timeout=10,
    ) as ws:
        async def send(m): await ws.send(msgpack.packb(m, use_bin_type=True))
        async def recv(): return msgpack.unpackb(await ws.recv(), raw=False)

        await send({"t": "Hello", "v": {
            "protocol_version": 1, "client_version": "fp_bench/0.1",
            "persona_seed": sid,
        }})
        await recv()  # Welcome

        for i in range(probes):
            cid_base = 1 + i * 2
            t0 = time.perf_counter()
            ops, bytes_ = await one_probe(send, recv, cid_base)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
            counters["ops"] += ops
            counters["pixel_bytes"] += bytes_
            counters["probes"] += 1


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://127.0.0.1:8443")
    p.add_argument("--auth", default="user:secret")
    p.add_argument("--sessions", type=int, default=1024)
    p.add_argument("--probes", type=int, default=50,
                   help="fpjs probes per session")
    args = p.parse_args()

    ops_per_probe = len(text_canvas_ops()) + len(geom_canvas_ops())
    print(f"fp_bench: {args.sessions} concurrent sessions × {args.probes} fpjs probes")
    print(f"          ops/probe = {ops_per_probe} (text canvas + geometry canvas)")
    print(f"          total probes: {args.sessions * args.probes}")

    counters = {"ops": 0, "pixel_bytes": 0, "probes": 0}
    latencies_ms = []

    t0 = time.perf_counter()
    await asyncio.gather(*[
        session_worker(args.url, args.auth, sid, args.probes, latencies_ms, counters)
        for sid in range(args.sessions)
    ])
    elapsed = time.perf_counter() - t0

    print()
    print(f"=== throughput (wall: {elapsed:.2f}s) ===")
    print(f"  probes/sec      : {counters['probes'] / elapsed:>10,.0f}")
    print(f"  ops/sec         : {counters['ops'] / elapsed:>10,.0f}")
    mb = counters["pixel_bytes"] / (1024 * 1024)
    print(f"  pixel MB        : {mb:>10,.1f} MB ({mb / elapsed:.1f} MB/s)")
    print()

    if latencies_ms:
        latencies_ms.sort()
        n = len(latencies_ms)
        def pct(p): return latencies_ms[min(n - 1, int(n * p / 100))]
        print("=== per-probe latency (full fpjs canvas probe roundtrip) ===")
        print(f"  min   : {min(latencies_ms):>7.2f} ms")
        print(f"  p50   : {pct(50):>7.2f} ms")
        print(f"  p90   : {pct(90):>7.2f} ms")
        print(f"  p99   : {pct(99):>7.2f} ms")
        print(f"  max   : {max(latencies_ms):>7.2f} ms")
        print(f"  mean  : {statistics.mean(latencies_ms):>7.2f} ms")


if __name__ == "__main__":
    asyncio.run(main())
