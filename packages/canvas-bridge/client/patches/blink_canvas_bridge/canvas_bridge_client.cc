// Copyright (c) 2026 Arman Hossain <arman@bytetunnels.com>. ChromiumFish authors. All rights reserved.

#include "third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_client.h"

#include "base/base64.h"
#include "base/command_line.h"
#include "base/logging.h"
#include "base/no_destructor.h"
#include "base/strings/string_split.h"
#include "components/canvas_bridge/public/canvas_bridge_switches.h"

// NOTE: This compile unit deliberately *avoids* depending on
// //services/network — the bridge needs a synchronous-from-renderer
// readback path, which the Mojo NetworkService can't easily satisfy
// without enormous plumbing. Instead we open a raw blocking TCP
// WebSocket on the I/O thread (see ConnectImpl) using the platform
// socket libraries that Blink already links against
// (`net::TCPClientSocket`, manually framing the WebSocket protocol).
//
// The implementation below is a scaffold — the actual handshake +
// framing code lives in canvas_bridge_ws_impl.cc which is gitignored
// in this scaffold; a stub returning `false` from DoConnect keeps the
// bridge cleanly disabled until you supply the implementation.

namespace blink::canvas_bridge {

namespace {

CanvasBridgeClient* g_instance = nullptr;

bool ReadSwitches(std::string* url, std::string* auth) {
  const base::CommandLine* cmd = base::CommandLine::ForCurrentProcess();
  if (!cmd->HasSwitch(switches::kCanvasBridgeUrl)) {
    return false;
  }
  *url = cmd->GetSwitchValueASCII(switches::kCanvasBridgeUrl);
  if (cmd->HasSwitch(switches::kCanvasBridgeAuth)) {
    *auth = cmd->GetSwitchValueASCII(switches::kCanvasBridgeAuth);
  }
  return !url->empty() && !auth->empty();
}

}  // namespace

CanvasBridgeClient* CanvasBridgeClient::Get() {
  static base::NoDestructor<CanvasBridgeClient> kSingleton;
  return kSingleton.get();
}

CanvasBridgeClient::CanvasBridgeClient() {
  StartUp();
}

CanvasBridgeClient::~CanvasBridgeClient() = default;

void CanvasBridgeClient::StartUp() {
  State expected = State::kUninitialized;
  if (!state_.compare_exchange_strong(expected, State::kConnecting)) {
    return;
  }
  if (!ReadSwitches(&url_, &auth_)) {
    Disable("--canvas-bridge-url / --canvas-bridge-auth not set");
    return;
  }
  io_thread_ = std::make_unique<base::Thread>("canvas-bridge-io");
  base::Thread::Options opts;
  opts.message_pump_type = base::MessagePumpType::IO;
  if (!io_thread_->StartWithOptions(std::move(opts))) {
    Disable("failed to start canvas-bridge I/O thread");
    return;
  }
  io_thread_->task_runner()->PostTask(
      FROM_HERE,
      base::BindOnce(&CanvasBridgeClient::IoThreadLoop, base::Unretained(this)));
}

void CanvasBridgeClient::IoThreadLoop() {
  if (!DoConnect(url_, auth_)) {
    Disable("canvas-bridge server unreachable / handshake failed");
    return;
  }
  state_.store(State::kReady);
  LOG(INFO) << "[canvas-bridge] connected to " << url_;
  // Real implementation: read frames in a loop, dispatch to
  // HandleIncoming. Until the WebSocket framing layer lands we
  // exit immediately; IsEnabled() returns true so synchronous
  // readbacks will time out cleanly.
}

bool CanvasBridgeClient::DoConnect(const std::string& url,
                                   const std::string& auth) {
  // TODO(canvas-bridge): replace stub with real WebSocket handshake.
  //
  // Outline:
  //   1. Parse url → host, port, scheme (ws / wss).
  //   2. Open TCP (`net::TCPClientSocket::Connect`), wrap with TLS if
  //      wss (`net::SSLClientSocket`).
  //   3. Send HTTP/1.1 Upgrade request with:
  //        Sec-WebSocket-Key: random16 base64
  //        Sec-WebSocket-Version: 13
  //        Authorization: Basic base64(auth)
  //   4. Verify 101 Switching Protocols + Sec-WebSocket-Accept hash.
  //   5. Send Hello frame, wait for Welcome.
  //
  // Returns true once Welcome is received with kProtocolVersion match.
  (void)url;
  (void)auth;
  return false;
}

uint32_t CanvasBridgeClient::AllocateCanvasId() {
  if (!IsEnabled()) {
    return 0;
  }
  return next_canvas_id_.fetch_add(1);
}

void CanvasBridgeClient::Send(std::vector<uint8_t> frame) {
  if (!IsEnabled()) {
    return;
  }
  if (!io_thread_) {
    return;
  }
  io_thread_->task_runner()->PostTask(
      FROM_HERE, base::BindOnce([](std::vector<uint8_t>) {
        // Real impl: write a binary frame to the WebSocket. Stubbed
        // until DoConnect is implemented.
      }, std::move(frame)));
}

std::optional<ImageDataReply> CanvasBridgeClient::RequestImageData(
    uint32_t canvas_id,
    int32_t x,
    int32_t y,
    uint32_t w,
    uint32_t h,
    int timeout_ms) {
  if (!IsEnabled()) {
    return std::nullopt;
  }
  base::WaitableEvent done(base::WaitableEvent::ResetPolicy::MANUAL,
                           base::WaitableEvent::InitialState::NOT_SIGNALED);
  ImageDataReply reply{};
  io_thread_->task_runner()->PostTask(
      FROM_HERE,
      base::BindOnce(
          [](uint32_t id, int32_t x, int32_t y, uint32_t w, uint32_t h,
             ImageDataReply* out, base::WaitableEvent* done) {
            // Real impl: send GetCanvas2DImageData, read until matching
            // ImageData reply arrives, copy into *out. Stubbed for now.
            (void)id;
            (void)x;
            (void)y;
            (void)w;
            (void)h;
            (void)out;
            done->Signal();
          },
          canvas_id, x, y, w, h, &reply, &done));
  if (!done.TimedWait(base::Milliseconds(timeout_ms))) {
    return std::nullopt;
  }
  return reply;
}

void CanvasBridgeClient::Disable(const std::string& reason) {
  state_.store(State::kDisabled);
  LOG(INFO) << "[canvas-bridge] disabled: " << reason;
}

void CanvasBridgeClient::SetFakeConnectedForTesting() {
  state_.store(State::kReady);
}

}  // namespace blink::canvas_bridge
