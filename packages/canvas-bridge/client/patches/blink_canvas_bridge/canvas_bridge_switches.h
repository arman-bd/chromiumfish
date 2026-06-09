// Copyright (c) 2026 Arman Hossain <arman@bytetunnels.com>. ChromiumFish authors. All rights reserved.
//
// canvas-bridge command-line switches. Two flags, both optional. The
// browser process passes them through to renderers via
// AppendRendererCommandLine; the renderer's CanvasBridgeClient reads
// them at construction time to decide whether to open a WebSocket.

#ifndef COMPONENTS_CANVAS_BRIDGE_PUBLIC_CANVAS_BRIDGE_SWITCHES_H_
#define COMPONENTS_CANVAS_BRIDGE_PUBLIC_CANVAS_BRIDGE_SWITCHES_H_

namespace canvas_bridge::switches {

// `wss://host:port/path` — when present, the renderer opens a
// persistent connection to this URL for canvas / WebGL / font
// remoting. Missing = bridge stays dormant, browser renders locally.
extern const char kCanvasBridgeUrl[];

// `user:secret` — HTTP Basic credentials sent on the WebSocket
// upgrade. Required if kCanvasBridgeUrl is present.
extern const char kCanvasBridgeAuth[];

}  // namespace canvas_bridge::switches

#endif  // COMPONENTS_CANVAS_BRIDGE_PUBLIC_CANVAS_BRIDGE_SWITCHES_H_
