// Copyright (c) 2026 Arman Hossain <arman@bytetunnels.com>. ChromiumFish authors. All rights reserved.
//
// CanvasBridgeClient — per-renderer-process singleton that owns the
// WebSocket connection to the remote render server. Blink call sites
// (html_canvas_element.cc, base_rendering_context_2d.cc) call into
// this from the renderer main thread; the client thunks the request
// to its dedicated I/O thread, which speaks the protocol.
//
// Lifetime: created lazily on first IsEnabled() call. Returns false
// from IsEnabled() if the --canvas-bridge-url switch wasn't supplied
// or the initial Hello/Welcome handshake failed. Once disabled, stays
// disabled for the rest of the process.

#ifndef THIRD_PARTY_BLINK_RENDERER_PLATFORM_CANVAS_BRIDGE_CANVAS_BRIDGE_CLIENT_H_
#define THIRD_PARTY_BLINK_RENDERER_PLATFORM_CANVAS_BRIDGE_CANVAS_BRIDGE_CLIENT_H_

#include <atomic>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "base/synchronization/waitable_event.h"
#include "base/threading/thread.h"
#include "third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_codec.h"
#include "third_party/blink/renderer/platform/platform_export.h"
#include "third_party/blink/renderer/platform/wtf/text/wtf_string.h"

namespace blink::canvas_bridge {

class PLATFORM_EXPORT CanvasBridgeClient {
 public:
  // Returns the process-wide singleton. Always non-null; check
  // IsEnabled() before issuing ops.
  static CanvasBridgeClient* Get();

  // True iff the --canvas-bridge-url switch is set and the server
  // handshook successfully. Cheap to call from the renderer main
  // thread.
  bool IsEnabled() const { return state_.load() == State::kReady; }

  // Allocate a unique CanvasId for a new HTMLCanvasElement. Returns 0
  // if the bridge is disabled.
  uint32_t AllocateCanvasId();

  // Async fire-and-forget op send. The op is queued for the I/O thread.
  // No-op if disabled. Caller-owned buffer is copied.
  void Send(std::vector<uint8_t> frame);

  // Synchronous readback. Sends a GetCanvas2DImageData and blocks the
  // calling thread up to `timeout_ms` for the reply. Returns nullopt
  // on timeout / network error / disabled bridge.
  std::optional<ImageDataReply> RequestImageData(uint32_t canvas_id,
                                                  int32_t x,
                                                  int32_t y,
                                                  uint32_t w,
                                                  uint32_t h,
                                                  int timeout_ms = 5000);

  // Disable the bridge permanently. Called when an unrecoverable
  // protocol or network error occurs.
  void Disable(const std::string& reason);

  // Test seam.
  void SetFakeConnectedForTesting();

 private:
  enum class State : uint8_t { kUninitialized, kConnecting, kReady, kDisabled };

  CanvasBridgeClient();
  ~CanvasBridgeClient();

  void StartUp();         // called on main thread
  void IoThreadLoop();    // I/O thread entry

  // I/O thread methods.
  bool DoConnect(const std::string& url, const std::string& auth);
  void HandleIncoming(const std::vector<uint8_t>& frame);

  std::atomic<State> state_{State::kUninitialized};
  std::atomic<uint32_t> next_canvas_id_{1};

  std::unique_ptr<base::Thread> io_thread_;

  // Sync wait machinery for RequestImageData. Renderer thread signals
  // a request; I/O thread fulfills it and wakes the renderer.
  struct PendingReadback {
    uint32_t canvas_id;
    ImageDataReply reply;
    bool fulfilled = false;
    base::WaitableEvent done{
        base::WaitableEvent::ResetPolicy::MANUAL,
        base::WaitableEvent::InitialState::NOT_SIGNALED};
  };
  // I/O-thread-only: in-flight readbacks indexed by canvas_id.
  // Renderer-side wrappers use base::WaitableEvent for the cross-
  // thread signal.

  std::string url_;
  std::string auth_;
  uint64_t persona_seed_ = 0;
};

}  // namespace blink::canvas_bridge

#endif  // THIRD_PARTY_BLINK_RENDERER_PLATFORM_CANVAS_BRIDGE_CANVAS_BRIDGE_CLIENT_H_
