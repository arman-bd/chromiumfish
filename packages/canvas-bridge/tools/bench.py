"""canvas-bridge throughput / latency benchmark.

Spawns N concurrent sessions, each issuing a configurable canvas2d
op workload. Measures:

  * ops/sec  — total ops divided by wall-clock time
  * pixels/sec  — total RGBA bytes pulled back
  * latency p50, p90, p99 per full canvas roundtrip (CreateCanvas →
    BatchOps → GetImageData → reply)

Usage:
    pip install msgpack websockets numpy

    # 1. Start server in another shell:
    cargo run --release -- --listen 127.0.0.1:8443 --auth user:secret

    # 2. Then:
    python3 bench.py --sessions 64 --iters 200 --ops 32

`--ops` controls how many fillRect ops each iteration issues (so the
server actually does work, not just bounce empty frames). `--iters`
is how many full canvas roundtrips each session runs in series.
Total ops shipped = sessions * iters * ops.
"""

import argparse
import asyncio
import base64
import os
import statistics
import time

import msgpack
import websockets


def b64_basic(creds: str) -> str:
    return base64.b64encode(creds.encode()).decode()


async def session_worker(
    url: str,
    creds: str,
    sid: int,
    iters: int,
    ops_per_iter: int,
    width: int,
    height: int,
    latencies_ms: list,
    counters: dict,
):
    headers = {"Authorization": f"Basic {b64_basic(creds)}"}
    async with websockets.connect(url, additional_headers=headers, max_size=2**24) as ws:
        async def send(m):
            await ws.send(msgpack.packb(m, use_bin_type=True))

        async def recv():
            return msgpack.unpackb(await ws.recv(), raw=False)

        # Handshake.
        await send({"t": "Hello", "v": {
            "protocol_version": 1,
            "client_version": "bench/0.1",
            "persona_seed": sid,
        }})
        welcome = await recv()
        assert welcome.get("t") == "Welcome", welcome

        for i in range(iters):
            canvas_id = i + 1  # unique per iter within session
            await send({"t": "CreateCanvas2D", "v": {
                "id": canvas_id, "width": width, "height": height, "opaque": True,
            }})

            # Build N fillRect ops in one batch — exercises the
            # path the browser hits during fpjs's canvas probe.
            batch_ops = []
            for j in range(ops_per_iter):
                if j % 2 == 0:
                    color = f"#{(j * 23) & 0xff:02x}{(j * 71) & 0xff:02x}{(j * 191) & 0xff:02x}"
                    batch_ops.append(
                        {"op": "SetFillStyle", "args": {"k": "Color", "v": color}}
                    )
                else:
                    batch_ops.append(
                        {"op": "FillRect", "args": {
                            "x": float((j * 7) % width),
                            "y": float((j * 13) % height),
                            "w": float(5 + (j * 3) % 20),
                            "h": float(5 + (j * 5) % 20),
                        }}
                    )

            t0 = time.perf_counter()
            await send({"t": "Canvas2DBatch", "v": {
                "id": canvas_id, "ops": batch_ops,
            }})
            await send({"t": "GetCanvas2DImageData", "v": {
                "id": canvas_id, "x": 0, "y": 0, "w": width, "h": height,
            }})
            reply = await recv()
            t1 = time.perf_counter()

            assert reply.get("t") == "ImageData", reply
            pixels = reply["v"]["pixels"]
            counters["pixel_bytes"] += len(pixels)
            counters["ops"] += ops_per_iter
            counters["roundtrips"] += 1
            latencies_ms.append((t1 - t0) * 1000.0)

            await send({"t": "DestroyCanvas", "v": {"id": canvas_id}})


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://127.0.0.1:8443")
    p.add_argument("--auth", default="user:secret")
    p.add_argument("--sessions", type=int, default=32)
    p.add_argument("--iters", type=int, default=100,
                   help="canvas roundtrips per session")
    p.add_argument("--ops", type=int, default=32,
                   help="ops per batch within each canvas")
    p.add_argument("--width", type=int, default=240)
    p.add_argument("--height", type=int, default=60)
    args = p.parse_args()

    total_ops_expected = args.sessions * args.iters * args.ops
    total_round = args.sessions * args.iters
    print(f"bench: {args.sessions} sessions × {args.iters} canvases × {args.ops} ops")
    print(f"       total: {total_ops_expected} ops, {total_round} canvas roundtrips")
    print(f"       canvas: {args.width}×{args.height}, "
          f"{args.width * args.height * 4} bytes per readback")

    counters = {"ops": 0, "pixel_bytes": 0, "roundtrips": 0}
    latencies_ms = []

    t0 = time.perf_counter()
    await asyncio.gather(*[
        session_worker(
            args.url, args.auth, sid, args.iters, args.ops,
            args.width, args.height, latencies_ms, counters,
        )
        for sid in range(args.sessions)
    ])
    elapsed = time.perf_counter() - t0

    # Reports
    print()
    print(f"=== throughput (wall: {elapsed:.2f}s) ===")
    print(f"  ops/sec         : {counters['ops'] / elapsed:>10,.0f}")
    print(f"  roundtrips/sec  : {counters['roundtrips'] / elapsed:>10,.0f}")
    mb = counters["pixel_bytes"] / (1024 * 1024)
    print(f"  pixel MB pulled : {mb:>10,.1f} MB  ({mb / elapsed:.1f} MB/s)")
    print()

    if latencies_ms:
        latencies_ms.sort()
        n = len(latencies_ms)
        def pct(p): return latencies_ms[min(n - 1, int(n * p / 100))]
        print("=== canvas roundtrip latency (BatchOps + GetImageData) ===")
        print(f"  min   : {min(latencies_ms):>7.2f} ms")
        print(f"  p50   : {pct(50):>7.2f} ms")
        print(f"  p90   : {pct(90):>7.2f} ms")
        print(f"  p99   : {pct(99):>7.2f} ms")
        print(f"  max   : {max(latencies_ms):>7.2f} ms")
        print(f"  mean  : {statistics.mean(latencies_ms):>7.2f} ms")


if __name__ == "__main__":
    asyncio.run(main())
