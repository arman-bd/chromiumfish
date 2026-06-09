"""End-to-end equivalence test: run the same canvas2d op stream through

  (a) canvas-bridge-server, fetching raw RGBA via GetCanvas2DImageData
  (b) regular Chrome via CDP, fetching raw RGBA via canvas.getImageData

and assert the pixel buffers are byte-identical. This is the canonical
proof that the bridge's render path matches real Chrome — independent of
whatever PNG/JPEG container the browser eventually wraps the pixels in.

Usage:
    # 1. Run the server in another shell:
    #       cargo run --release -- --listen 127.0.0.1:8443 --auth user:secret
    # 2. Then:
    python3 compare_with_chrome.py

Prereqs:  pip install msgpack websockets
"""

import asyncio
import base64
import hashlib
import json
import os
import random
import subprocess
import tempfile
import urllib.request

import msgpack
import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BRIDGE_URL = os.environ.get("CANVAS_BRIDGE_URL", "ws://127.0.0.1:8443")
BRIDGE_AUTH = os.environ.get("CANVAS_BRIDGE_AUTH", "user:secret")

# The canvas2d op stream we replay on both sides. Keep this list as the
# single source of truth.
WIDTH, HEIGHT = 240, 60
OPS = [
    ("SetFillStyle", ("Color", "#ffffff")),
    ("FillRect", (0.0, 0.0, float(WIDTH), float(HEIGHT))),
    ("SetFillStyle", ("Color", "#ff0000")),
    ("FillRect", (10.0, 10.0, 50.0, 30.0)),
    ("SetFillStyle", ("Color", "#069")),
    ("SetFont", ("11px Arial",)),
    ("SetTextBaseline", ("alphabetic",)),
    ("FillText", ("Cwm fjordbank glyphs vext quiz", 80.0, 30.0, None)),
]


async def bridge_pixels() -> bytes:
    headers = {"Authorization": f"Basic {base64.b64encode(BRIDGE_AUTH.encode()).decode()}"}
    async with websockets.connect(BRIDGE_URL, additional_headers=headers, max_size=2**24) as ws:
        async def send(m): await ws.send(msgpack.packb(m, use_bin_type=True))
        async def recv(): return msgpack.unpackb(await ws.recv(), raw=False)

        await send({"t": "Hello", "v": {"protocol_version": 1, "client_version": "compare/0.1", "persona_seed": 0}})
        await recv()  # Welcome
        await send({"t": "CreateCanvas2D", "v": {"id": 1, "width": WIDTH, "height": HEIGHT, "opaque": True}})
        # Build batch in one frame.
        batch_ops = []
        for op_name, args in OPS:
            if op_name == "SetFillStyle":
                op = {"op": op_name, "args": {"k": args[0], "v": args[1]}}
            elif op_name == "FillRect":
                op = {"op": op_name, "args": {"x": args[0], "y": args[1], "w": args[2], "h": args[3]}}
            elif op_name == "SetFont":
                op = {"op": op_name, "args": args[0]}
            elif op_name == "SetTextBaseline":
                op = {"op": op_name, "args": args[0]}
            elif op_name == "SetTextAlign":
                op = {"op": op_name, "args": args[0]}
            elif op_name == "FillText":
                op = {"op": op_name, "args": {
                    "text": args[0], "x": args[1], "y": args[2], "max_width": args[3],
                }}
            else:
                raise RuntimeError(op_name)
            batch_ops.append(op)
        await send({"t": "Canvas2DBatch", "v": {"id": 1, "ops": batch_ops}})
        await send({"t": "GetCanvas2DImageData", "v": {"id": 1, "x": 0, "y": 0, "w": WIDTH, "h": HEIGHT}})
        reply = await recv()
        assert reply["t"] == "ImageData", reply
        return bytes(reply["v"]["pixels"])


async def chrome_pixels() -> bytes:
    port = random.randint(50000, 59999)
    tmp = tempfile.mkdtemp(prefix="chrome-cdp-")
    proc = subprocess.Popen(
        [CHROME, f"--user-data-dir={tmp}", f"--remote-debugging-port={port}",
         "--headless=new", "--disable-gpu", "--no-first-run",
         "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as r:
                    targets = json.load(r)
                    if any(t.get("type") == "page" for t in targets):
                        break
            except Exception:
                pass
            await asyncio.sleep(0.3)
        target = next(t for t in targets if t.get("type") == "page")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=2**24) as ws:
            mid = [0]
            async def cdp(method, params=None):
                mid[0] += 1
                await ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == mid[0]:
                        return r

            # Build the canvas2d ops as JavaScript that mirrors OPS.
            js_ops = []
            for op_name, args in OPS:
                if op_name == "SetFillStyle":
                    js_ops.append(f"ctx.fillStyle = {json.dumps(args[1])};")
                elif op_name == "FillRect":
                    js_ops.append(f"ctx.fillRect({args[0]}, {args[1]}, {args[2]}, {args[3]});")
                elif op_name == "SetFont":
                    js_ops.append(f"ctx.font = {json.dumps(args[0])};")
                elif op_name == "SetTextBaseline":
                    js_ops.append(f"ctx.textBaseline = {json.dumps(args[0])};")
                elif op_name == "SetTextAlign":
                    js_ops.append(f"ctx.textAlign = {json.dumps(args[0])};")
                elif op_name == "FillText":
                    if args[3] is None:
                        js_ops.append(f"ctx.fillText({json.dumps(args[0])}, {args[1]}, {args[2]});")
                    else:
                        js_ops.append(f"ctx.fillText({json.dumps(args[0])}, {args[1]}, {args[2]}, {args[3]});")
            js = f"""
                (function() {{
                    const c = document.createElement('canvas');
                    c.width = {WIDTH}; c.height = {HEIGHT};
                    const ctx = c.getContext('2d', {{ alpha: false }});
                    {' '.join(js_ops)}
                    const id = ctx.getImageData(0, 0, {WIDTH}, {HEIGHT});
                    // serialize Uint8ClampedArray as base64
                    const bin = String.fromCharCode.apply(null, id.data);
                    return btoa(bin);
                }})();
            """
            r = await cdp("Runtime.evaluate", {"expression": js, "returnByValue": True})
            val = r["result"]["result"]["value"]
            return base64.b64decode(val)
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


async def main():
    bridge_task = asyncio.create_task(bridge_pixels())
    chrome_task = asyncio.create_task(chrome_pixels())
    bridge, chrome = await asyncio.gather(bridge_task, chrome_task)
    print(f"bridge raw RGBA: {len(bridge)} bytes, sha256={hashlib.sha256(bridge).hexdigest()}")
    print(f"chrome raw RGBA: {len(chrome)} bytes, sha256={hashlib.sha256(chrome).hexdigest()}")
    if bridge == chrome:
        print("MATCH — canvas-bridge output is byte-identical to Chrome's getImageData")
        return 0
    else:
        diffs = sum(1 for i in range(0, len(bridge), 4) if bridge[i:i+4] != chrome[i:i+4])
        print(f"MISMATCH — {diffs} differing pixels of {len(bridge)//4}")
        # Show first 5 diffs
        n = 0
        for i in range(0, len(bridge), 4):
            if bridge[i:i+4] != chrome[i:i+4]:
                pi = i // 4
                x, y = pi % WIDTH, pi // WIDTH
                print(f"  ({x:3},{y:2}): bridge={tuple(bridge[i:i+4])} chrome={tuple(chrome[i:i+4])}")
                n += 1
                if n >= 5: break
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
