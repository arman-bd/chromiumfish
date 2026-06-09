// Copyright (c) 2026 Arman Hossain <arman@bytetunnels.com>. ChromiumFish authors. All rights reserved.

#include "third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_codec.h"

#include "base/check.h"
#include "base/notreached.h"

namespace blink::canvas_bridge {

namespace {

// Tiny hand-rolled msgpack writer for the subset of types we need
// (fixmap, str, bin, positive fixint, uint8/16/32, float32, bool).
// Keeps Blink free of a third-party msgpack dependency.

class Writer {
 public:
  Writer() = default;

  void U8(uint8_t v) { buf_.push_back(v); }

  // Tagged messages serialize as fixmap { "t": <tag>, "v": <payload> }.
  void StartEnvelope(const char* tag) {
    BeginMap(2);
    Str("t");
    Str(tag);
    Str("v");
    // Caller writes the payload (a map) next.
  }

  void BeginMap(uint32_t n) {
    if (n <= 0x0f) {
      U8(0x80 | static_cast<uint8_t>(n));
    } else if (n <= 0xffff) {
      U8(0xde);
      U16(n);
    } else {
      U8(0xdf);
      U32(n);
    }
  }

  void Str(const char* s) { Str(std::string(s)); }
  void Str(const std::string& s) {
    if (s.size() <= 31) {
      U8(0xa0 | static_cast<uint8_t>(s.size()));
    } else if (s.size() <= 0xff) {
      U8(0xd9);
      U8(static_cast<uint8_t>(s.size()));
    } else if (s.size() <= 0xffff) {
      U8(0xda);
      U16(static_cast<uint16_t>(s.size()));
    } else {
      U8(0xdb);
      U32(static_cast<uint32_t>(s.size()));
    }
    buf_.insert(buf_.end(), s.begin(), s.end());
  }

  void StrUtf8(const String& s) { Str(s.Utf8()); }

  void Bin(const uint8_t* data, size_t n) {
    if (n <= 0xff) {
      U8(0xc4);
      U8(static_cast<uint8_t>(n));
    } else if (n <= 0xffff) {
      U8(0xc5);
      U16(static_cast<uint16_t>(n));
    } else {
      U8(0xc6);
      U32(static_cast<uint32_t>(n));
    }
    buf_.insert(buf_.end(), data, data + n);
  }

  void Uint(uint64_t v) {
    if (v <= 0x7f) {
      U8(static_cast<uint8_t>(v));
    } else if (v <= 0xff) {
      U8(0xcc);
      U8(static_cast<uint8_t>(v));
    } else if (v <= 0xffff) {
      U8(0xcd);
      U16(static_cast<uint16_t>(v));
    } else if (v <= 0xffffffffULL) {
      U8(0xce);
      U32(static_cast<uint32_t>(v));
    } else {
      U8(0xcf);
      U64(v);
    }
  }

  void Int32(int32_t v) {
    if (v >= 0) {
      Uint(static_cast<uint64_t>(v));
    } else {
      U8(0xd2);
      U32(static_cast<uint32_t>(v));
    }
  }

  void Float32(float v) {
    U8(0xca);
    uint32_t bits;
    static_assert(sizeof(bits) == sizeof(v));
    std::memcpy(&bits, &v, sizeof(bits));
    U32(bits);
  }

  void Bool(bool v) { U8(v ? 0xc3 : 0xc2); }
  void Null() { U8(0xc0); }

  std::vector<uint8_t> Take() && { return std::move(buf_); }

 private:
  void U16(uint16_t v) {
    U8(static_cast<uint8_t>(v >> 8));
    U8(static_cast<uint8_t>(v));
  }
  void U32(uint32_t v) {
    U8(static_cast<uint8_t>(v >> 24));
    U8(static_cast<uint8_t>(v >> 16));
    U8(static_cast<uint8_t>(v >> 8));
    U8(static_cast<uint8_t>(v));
  }
  void U64(uint64_t v) {
    U32(static_cast<uint32_t>(v >> 32));
    U32(static_cast<uint32_t>(v));
  }

  std::vector<uint8_t> buf_;
};

// Writes the canonical Canvas2DOp envelope: { id, op: { op: <name>, args: <args> } }.
void WriteCanvas2DOpHeader(Writer& w,
                           uint32_t id,
                           const char* op_name) {
  w.StartEnvelope("Canvas2DOp");
  w.BeginMap(2);
  w.Str("id");
  w.Uint(id);
  w.Str("op");
  w.BeginMap(2);
  w.Str("op");
  w.Str(op_name);
  w.Str("args");
}

}  // namespace

std::vector<uint8_t> MsgBuilder::Hello(const std::string& client_version,
                                       uint64_t persona_seed) {
  Writer w;
  w.StartEnvelope("Hello");
  w.BeginMap(3);
  w.Str("protocol_version");
  w.Uint(kProtocolVersion);
  w.Str("client_version");
  w.Str(client_version);
  w.Str("persona_seed");
  w.Uint(persona_seed);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::CreateCanvas2D(uint32_t id,
                                                 uint32_t width,
                                                 uint32_t height,
                                                 bool opaque) {
  Writer w;
  w.StartEnvelope("CreateCanvas2D");
  w.BeginMap(4);
  w.Str("id");
  w.Uint(id);
  w.Str("width");
  w.Uint(width);
  w.Str("height");
  w.Uint(height);
  w.Str("opaque");
  w.Bool(opaque);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::SetFillStyleColor(uint32_t id,
                                                    const String& css) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "SetFillStyle");
  w.BeginMap(2);
  w.Str("k");
  w.Str("Color");
  w.Str("v");
  w.StrUtf8(css);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::SetStrokeStyleColor(uint32_t id,
                                                      const String& css) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "SetStrokeStyle");
  w.BeginMap(2);
  w.Str("k");
  w.Str("Color");
  w.Str("v");
  w.StrUtf8(css);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::SetFont(uint32_t id, const String& font) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "SetFont");
  w.StrUtf8(font);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::SetTextAlign(uint32_t id, const String& align) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "SetTextAlign");
  w.StrUtf8(align);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::SetTextBaseline(uint32_t id,
                                                  const String& baseline) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "SetTextBaseline");
  w.StrUtf8(baseline);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::FillRect(uint32_t id,
                                           float x,
                                           float y,
                                           float w_,
                                           float h_) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "FillRect");
  w.BeginMap(4);
  w.Str("x");
  w.Float32(x);
  w.Str("y");
  w.Float32(y);
  w.Str("w");
  w.Float32(w_);
  w.Str("h");
  w.Float32(h_);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::StrokeRect(uint32_t id,
                                             float x,
                                             float y,
                                             float w_,
                                             float h_) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "StrokeRect");
  w.BeginMap(4);
  w.Str("x");
  w.Float32(x);
  w.Str("y");
  w.Float32(y);
  w.Str("w");
  w.Float32(w_);
  w.Str("h");
  w.Float32(h_);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::FillText(uint32_t id,
                                           const String& text,
                                           float x,
                                           float y,
                                           std::optional<float> max_width) {
  Writer w;
  WriteCanvas2DOpHeader(w, id, "FillText");
  w.BeginMap(4);
  w.Str("text");
  w.StrUtf8(text);
  w.Str("x");
  w.Float32(x);
  w.Str("y");
  w.Float32(y);
  w.Str("max_width");
  if (max_width.has_value()) {
    w.Float32(*max_width);
  } else {
    w.Null();
  }
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::GetCanvas2DImageData(uint32_t id,
                                                       int32_t x,
                                                       int32_t y,
                                                       uint32_t w_,
                                                       uint32_t h_) {
  Writer w;
  w.StartEnvelope("GetCanvas2DImageData");
  w.BeginMap(5);
  w.Str("id");
  w.Uint(id);
  w.Str("x");
  w.Int32(x);
  w.Str("y");
  w.Int32(y);
  w.Str("w");
  w.Uint(w_);
  w.Str("h");
  w.Uint(h_);
  return std::move(w).Take();
}

std::vector<uint8_t> MsgBuilder::DestroyCanvas(uint32_t id) {
  Writer w;
  w.StartEnvelope("DestroyCanvas");
  w.BeginMap(1);
  w.Str("id");
  w.Uint(id);
  return std::move(w).Take();
}

/* ---------------- parser ---------------- */

namespace {

// Minimal msgpack reader. Returns false on malformed input. Supports
// only the subset our server emits.
class Reader {
 public:
  Reader(base::span<const uint8_t> buf) : buf_(buf) {}

  bool ReadMapHeader(uint32_t* n) {
    if (Empty()) return false;
    uint8_t t = Next();
    if ((t & 0xf0) == 0x80) {
      *n = t & 0x0f;
      return true;
    }
    if (t == 0xde) return Read16(n);
    if (t == 0xdf) return Read32(n);
    return false;
  }

  bool ReadStr(std::string* out) {
    if (Empty()) return false;
    uint8_t t = Next();
    uint32_t n = 0;
    if ((t & 0xe0) == 0xa0) {
      n = t & 0x1f;
    } else if (t == 0xd9) {
      uint8_t v;
      if (!Read8(&v)) return false;
      n = v;
    } else if (t == 0xda) {
      uint16_t v;
      if (!Read16(&v)) return false;
      n = v;
    } else if (t == 0xdb) {
      uint32_t v;
      if (!Read32(&v)) return false;
      n = v;
    } else {
      return false;
    }
    if (buf_.size() < n) return false;
    out->assign(reinterpret_cast<const char*>(buf_.data()),
                reinterpret_cast<const char*>(buf_.data()) + n);
    buf_ = buf_.subspan(n);
    return true;
  }

  bool ReadBin(std::vector<uint8_t>* out) {
    if (Empty()) return false;
    uint8_t t = Next();
    uint32_t n = 0;
    if (t == 0xc4) {
      uint8_t v;
      if (!Read8(&v)) return false;
      n = v;
    } else if (t == 0xc5) {
      uint16_t v;
      if (!Read16(&v)) return false;
      n = v;
    } else if (t == 0xc6) {
      if (!Read32(&n)) return false;
    } else {
      return false;
    }
    if (buf_.size() < n) return false;
    out->assign(buf_.data(), buf_.data() + n);
    buf_ = buf_.subspan(n);
    return true;
  }

  bool ReadUint(uint64_t* out) {
    if (Empty()) return false;
    uint8_t t = Next();
    if ((t & 0x80) == 0) {
      *out = t;
      return true;
    }
    switch (t) {
      case 0xcc: {
        uint8_t v;
        if (!Read8(&v)) return false;
        *out = v;
        return true;
      }
      case 0xcd: {
        uint16_t v;
        if (!Read16(&v)) return false;
        *out = v;
        return true;
      }
      case 0xce: {
        uint32_t v;
        if (!Read32(&v)) return false;
        *out = v;
        return true;
      }
      case 0xcf: {
        uint64_t v;
        if (!Read64(&v)) return false;
        *out = v;
        return true;
      }
      default:
        return false;
    }
  }

  // Skip one value (any type). Returns false on malformed input.
  bool Skip();

 private:
  bool Empty() const { return buf_.empty(); }
  uint8_t Next() {
    uint8_t v = buf_[0];
    buf_ = buf_.subspan(1);
    return v;
  }
  bool Read8(uint8_t* v) {
    if (buf_.empty()) return false;
    *v = buf_[0];
    buf_ = buf_.subspan(1);
    return true;
  }
  bool Read16(uint16_t* v) {
    if (buf_.size() < 2) return false;
    *v = (static_cast<uint16_t>(buf_[0]) << 8) | buf_[1];
    buf_ = buf_.subspan(2);
    return true;
  }
  bool Read16(uint32_t* v) {
    uint16_t x;
    if (!Read16(&x)) return false;
    *v = x;
    return true;
  }
  bool Read32(uint32_t* v) {
    if (buf_.size() < 4) return false;
    *v = (static_cast<uint32_t>(buf_[0]) << 24) |
         (static_cast<uint32_t>(buf_[1]) << 16) |
         (static_cast<uint32_t>(buf_[2]) << 8) | buf_[3];
    buf_ = buf_.subspan(4);
    return true;
  }
  bool Read64(uint64_t* v) {
    uint32_t hi, lo;
    if (!Read32(&hi) || !Read32(&lo)) return false;
    *v = (static_cast<uint64_t>(hi) << 32) | lo;
    return true;
  }
  base::span<const uint8_t> buf_;
};

bool Reader::Skip() {
  if (buf_.empty()) return false;
  uint8_t t = buf_[0];
  std::string s;
  std::vector<uint8_t> b;
  uint64_t u;
  if (t == 0xc0 || t == 0xc2 || t == 0xc3) {
    buf_ = buf_.subspan(1);
    return true;
  }
  if ((t & 0xe0) == 0xa0 || t == 0xd9 || t == 0xda || t == 0xdb) {
    return ReadStr(&s);
  }
  if (t == 0xc4 || t == 0xc5 || t == 0xc6) {
    return ReadBin(&b);
  }
  if ((t & 0x80) == 0 || (t >= 0xcc && t <= 0xcf)) {
    return ReadUint(&u);
  }
  if ((t & 0xf0) == 0x80 || t == 0xde || t == 0xdf) {
    uint32_t n;
    if (!ReadMapHeader(&n)) return false;
    for (uint32_t i = 0; i < n * 2; ++i) {
      if (!Skip()) return false;
    }
    return true;
  }
  // Other types (arrays, floats, signed ints) — skip with a simple
  // fall-through that's good enough for the messages we expect.
  NOTREACHED();
  return false;
}

}  // namespace

std::optional<WelcomeReply> MsgParser::ParseWelcome(
    base::span<const uint8_t> frame) {
  Reader r(frame);
  uint32_t n = 0;
  if (!r.ReadMapHeader(&n) || n != 2) return std::nullopt;
  std::string key;
  if (!r.ReadStr(&key) || key != "t") return std::nullopt;
  std::string tag;
  if (!r.ReadStr(&tag) || tag != "Welcome") return std::nullopt;
  if (!r.ReadStr(&key) || key != "v") return std::nullopt;
  uint32_t pn = 0;
  if (!r.ReadMapHeader(&pn)) return std::nullopt;
  WelcomeReply out{};
  for (uint32_t i = 0; i < pn; ++i) {
    std::string k;
    if (!r.ReadStr(&k)) return std::nullopt;
    if (k == "protocol_version") {
      uint64_t v;
      if (!r.ReadUint(&v)) return std::nullopt;
      out.protocol_version = static_cast<uint32_t>(v);
    } else if (k == "server_version") {
      if (!r.ReadStr(&out.server_version)) return std::nullopt;
    } else if (k == "os") {
      if (!r.ReadStr(&out.os)) return std::nullopt;
    } else if (k == "gpu_renderer") {
      if (!r.ReadStr(&out.gpu_renderer)) return std::nullopt;
    } else if (k == "gpu_vendor") {
      if (!r.ReadStr(&out.gpu_vendor)) return std::nullopt;
    } else {
      if (!r.Skip()) return std::nullopt;
    }
  }
  return out;
}

std::optional<ImageDataReply> MsgParser::ParseImageData(
    base::span<const uint8_t> frame) {
  Reader r(frame);
  uint32_t n = 0;
  if (!r.ReadMapHeader(&n) || n != 2) return std::nullopt;
  std::string key;
  if (!r.ReadStr(&key) || key != "t") return std::nullopt;
  std::string tag;
  if (!r.ReadStr(&tag) || tag != "ImageData") return std::nullopt;
  if (!r.ReadStr(&key) || key != "v") return std::nullopt;
  uint32_t pn = 0;
  if (!r.ReadMapHeader(&pn)) return std::nullopt;
  ImageDataReply out{};
  for (uint32_t i = 0; i < pn; ++i) {
    std::string k;
    if (!r.ReadStr(&k)) return std::nullopt;
    if (k == "id") {
      uint64_t v;
      if (!r.ReadUint(&v)) return std::nullopt;
      out.canvas_id = static_cast<uint32_t>(v);
    } else if (k == "w") {
      uint64_t v;
      if (!r.ReadUint(&v)) return std::nullopt;
      out.width = static_cast<uint32_t>(v);
    } else if (k == "h") {
      uint64_t v;
      if (!r.ReadUint(&v)) return std::nullopt;
      out.height = static_cast<uint32_t>(v);
    } else if (k == "pixels") {
      if (!r.ReadBin(&out.pixels)) return std::nullopt;
    } else {
      if (!r.Skip()) return std::nullopt;
    }
  }
  return out;
}

}  // namespace blink::canvas_bridge
