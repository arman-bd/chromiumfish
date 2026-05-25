// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef THIRD_PARTY_BLINK_PUBLIC_COMMON_FINGERPRINTING_FINGERPRINT_AUDIO_ISOLATION_H_
#define THIRD_PARTY_BLINK_PUBLIC_COMMON_FINGERPRINTING_FINGERPRINT_AUDIO_ISOLATION_H_

#include <stdint.h>

#include "base/containers/span.h"
#include "third_party/blink/public/common/common_export.h"

namespace blink::fingerprinting {

// Adds per-seed deterministic ultra-low-amplitude noise to a span of audio
// samples (interleaved or planar — the routine treats it as a flat span of
// float32 samples). The noise is keyed on (sample_index, persona_seed) and
// stays at ~1e-7 amplitude — well below the threshold of human perception
// and below most DSP processing noise floors, but large enough that the
// IEEE-754 byte representation of every sample changes.
//
// Why: fpjs Pro and CreepJS both probe AudioContext / OfflineAudioContext
// by rendering a fixed signal (triangle wave through a DynamicsCompressor)
// and summing the absolute values of the result. Stock Chrome with
// SwiftShader (every headless cloud Chrome on a GPU-less Linux VPS) emits
// the same audio bytes byte-for-byte, so the resulting sum is a constant
// (124.04347527516074) that uniquely identifies "headless SwiftShader
// Chrome." Adding per-persona-seed noise changes that sum into a per-seed
// stable value, breaking the SwiftShader cluster signature.
//
// Same seed → same noise pattern → same audio fingerprint hash (so
// cross-session anonymity is preserved for the same persona). Different
// seeds → different patterns → different hashes (so users with rotated
// personas don't cross-link via audio).
//
// `sample_offset` is the global index of `samples[0]` in the overall
// stream — OfflineAudioContext renders the destination in fixed-size
// quanta (typically 128 samples), and the caller must thread the
// running per-channel sample count through so the noise key never
// resets between quanta. If it does, the per-quantum noise pattern
// repeats every quantum-size samples and the integrated sum that
// fpjs Pro measures cancels out to the original value (the bug we
// fix here — empirically observed on the first integration attempt).
BLINK_COMMON_EXPORT void IsolateAudioSamples(base::span<float> samples,
                                             uint64_t sample_offset,
                                             uint64_t persona_seed);

}  // namespace blink::fingerprinting

#endif  // THIRD_PARTY_BLINK_PUBLIC_COMMON_FINGERPRINTING_FINGERPRINT_AUDIO_ISOLATION_H_
