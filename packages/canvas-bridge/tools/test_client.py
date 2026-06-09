#!/usr/bin/env python3
"""Smoke-test client for canvas-bridge-server.

Speaks the same WebSocket+msgpack protocol the browser will speak, so we
can exercise the server without rebuilding ChromiumFish each iteration.

Usage:
    pip install websockets msgpack
    python3 test_client.py ws://localhost:8443 user:secret
"""

import asyncio
import base64
import sys

import msgpack
import websockets


def b64_basic(creds: str) -> str:
    return base64.b64encode(creds.encode()).decode()


async def main(url: str, creds: str) -> None:
    headers = {"Authorization": f"Basic {b64_basic(creds)}"}
    print(f"→ connecting to {url}", flush=True)
    async with websockets.connect(url, additional_headers=headers, max_size=2**24) as ws:
        async def send(msg: dict) -> None:
            await ws.send(msgpack.packb(msg, use_bin_type=True))

        async def recv() -> dict:
            data = await ws.recv()
            return msgpack.unpackb(data, raw=False)

        await send({"t": "Hello", "v": {
            "protocol_version": 1,
            "client_version": "test_client.py/0.1",
            "persona_seed": 0xC0FFEE,
        }})
        welcome = await recv()
        print(f"← {welcome}", flush=True)

        # Push semantics: ops are fire-and-forget; we don't await
        # acks. Only readbacks (Get*, MeasureText) get replies.
        await send({"t": "CreateCanvas2D", "v": {
            "id": 1, "width": 240, "height": 60, "opaque": True,
        }})

        await send({"t": "Canvas2DBatch", "v": {
            "id": 1,
            "ops": [
                {"op": "SetFillStyle", "args": {"k": "Color", "v": "#ff0000"}},
                {"op": "FillRect", "args": {"x": 10.0, "y": 10.0, "w": 50.0, "h": 30.0}},
            ],
        }})

        # Canonical canvas readback for browser integration: raw RGBA
        # pixels via GetCanvas2DImageData. The browser-side patch will
        # pipe these through Chrome's own libpng so the final PNG bytes
        # match real Chrome by construction.
        await send({"t": "GetCanvas2DImageData", "v": {
            "id": 1, "x": 0, "y": 0, "w": 240, "h": 60,
        }})
        result = await recv()
        if result.get("t") == "ImageData":
            pixels = result["v"]["pixels"]
            out = "/tmp/canvas_bridge_pixels.rgba"
            with open(out, "wb") as f:
                f.write(pixels)
            print(f"← ImageData: {len(pixels)} bytes raw RGBA -> {out}", flush=True)
        else:
            print(f"← unexpected: {result}", flush=True)

        # Convenience: server-encoded PNG. Useful for visual inspection
        # during testing. NOT the path the browser-side patch will use.
        await send({"t": "GetCanvas2DPng", "v": {
            "id": 1, "mime": "image/png", "quality": 1.0,
        }})
        result = await recv()
        if result.get("t") == "CanvasPng":
            png = result["v"]["bytes"]
            out = "/tmp/canvas_bridge_test.png"
            with open(out, "wb") as f:
                f.write(png)
            print(f"← CanvasPng: {len(png)} bytes -> {out} (test convenience)", flush=True)

        # Font metric query
        await send({"t": "MeasureText", "v": {
            "text": "Cwm fjordbank glyphs vext quiz",
            "families": ["Arial", "Times New Roman", "Courier New"],
            "sizes_px": [12.0, 16.0, 24.0],
        }})
        m = await recv()
        print(f"← MeasureText: {m}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
