// Copyright (c) 2026 Arman Hossain <arman@bytetunnels.com>. ChromiumFish authors. All rights reserved.
//
// msgpack codec for the canvas-bridge wire protocol. Mirrors
// `canvas-bridge/proto/src/lib.rs` so the server can decode what
// we send.

#ifndef THIRD_PARTY_BLINK_RENDERER_PLATFORM_CANVAS_BRIDGE_CANVAS_BRIDGE_CODEC_H_
#define THIRD_PARTY_BLINK_RENDERER_PLATFORM_CANVAS_BRIDGE_CANVAS_BRIDGE_CODEC_H_

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "base/containers/span.h"
#include "third_party/blink/renderer/platform/platform_export.h"
#include "third_party/blink/renderer/platform/wtf/text/wtf_string.h"

namespace blink::canvas_bridge {

constexpr uint32_t kProtocolVersion = 1;

// Builder for outgoing ClientMsg frames. Each method allocates a new
// msgpack-encoded buffer; callers ship the result over the WebSocket
// binary channel.
class PLATFORM_EXPORT MsgBuilder {
 public:
  static std::vector<uint8_t> Hello(const std::string& client_version,
                                    uint64_t persona_seed);

  static std::vector<uint8_t> CreateCanvas2D(uint32_t id,
                                             uint32_t width,
                                             uint32_t height,
                                             bool opaque);

  // Op-stream messages
  static std::vector<uint8_t> SetFillStyleColor(uint32_t id, const String& css);
  static std::vector<uint8_t> SetStrokeStyleColor(uint32_t id,
                                                  const String& css);
  static std::vector<uint8_t> SetFont(uint32_t id, const String& font);
  static std::vector<uint8_t> SetTextAlign(uint32_t id, const String& align);
  static std::vector<uint8_t> SetTextBaseline(uint32_t id,
                                              const String& baseline);
  static std::vector<uint8_t> FillRect(uint32_t id,
                                       float x,
                                       float y,
                                       float w,
                                       float h);
  static std::vector<uint8_t> StrokeRect(uint32_t id,
                                         float x,
                                         float y,
                                         float w,
                                         float h);
  static std::vector<uint8_t> FillText(uint32_t id,
                                       const String& text,
                                       float x,
                                       float y,
                                       std::optional<float> max_width);

  // Readback
  static std::vector<uint8_t> GetCanvas2DImageData(uint32_t id,
                                                   int32_t x,
                                                   int32_t y,
                                                   uint32_t w,
                                                   uint32_t h);
  static std::vector<uint8_t> DestroyCanvas(uint32_t id);
};

// Parsed result of an `ImageData` server reply.
struct PLATFORM_EXPORT ImageDataReply {
  uint32_t canvas_id;
  uint32_t width;
  uint32_t height;
  std::vector<uint8_t> pixels;  // RGBA8, premultiplied per canvas spec
};

// Parsed result of a `Welcome` server reply.
struct PLATFORM_EXPORT WelcomeReply {
  uint32_t protocol_version;
  std::string server_version;
  std::string os;
  std::string gpu_renderer;
  std::string gpu_vendor;
};

class PLATFORM_EXPORT MsgParser {
 public:
  // Returns `std::nullopt` if `frame` is not a Welcome message or is
  // malformed.
  static std::optional<WelcomeReply> ParseWelcome(
      base::span<const uint8_t> frame);

  // Returns nullopt if `frame` is not an ImageData reply.
  static std::optional<ImageDataReply> ParseImageData(
      base::span<const uint8_t> frame);
};

}  // namespace blink::canvas_bridge

#endif  // THIRD_PARTY_BLINK_RENDERER_PLATFORM_CANVAS_BRIDGE_CANVAS_BRIDGE_CODEC_H_
