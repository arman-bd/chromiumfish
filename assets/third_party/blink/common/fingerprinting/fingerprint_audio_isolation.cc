// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "third_party/blink/public/common/fingerprinting/fingerprint_audio_isolation.h"

#include <cstddef>
#include <cstdint>

namespace blink::fingerprinting {

namespace {

// Deterministic 32-bit hash of (index, salt). Same mix kernel as the
// canvas isolation routine — well-distributed for the sample-count ×
// persona-space we care about, not cryptographic.
inline uint32_t NoiseAt(uint32_t index, uint32_t seed_salt) {
  uint32_t h = index * 2654435761u + seed_salt * 1597334677u;
  h ^= h >> 16;
  h *= 0x85ebca6bu;
  h ^= h >> 13;
  return h;
}

}  // namespace

void IsolateAudioSamples(base::span<float> samples,
                         uint64_t sample_offset,
                         uint64_t persona_seed) {
  // Fold the 64-bit persona seed into a 32-bit salt for the noise mix.
  // Mirrors the canvas isolation salt derivation so the two surfaces use
  // a consistent per-seed perturbation strategy.
  const uint32_t seed_salt =
      static_cast<uint32_t>(persona_seed) ^
      static_cast<uint32_t>(persona_seed >> 32);

  // 2026-06-01 redesign. The original code added zero-mean noise
  // [-amplitude, +amplitude] independently per sample. fpjs's audio
  // fingerprint probe sums Math.abs(sample[i]) over a long window —
  // zero-mean noise integrates to ~0 over that window, so the sum
  // stayed at the SwiftShader-deterministic 124.04347527516074 no
  // matter what persona seed we used, and fpjs re-identified every
  // persona as the same visitor_id. (Measured empirically: 5 different
  // --persona-seed values all produced the same fpjs.audio value.)
  //
  // New design: combine a per-seed CONSTANT multiplicative bias with
  // the per-sample noise. The bias is a single float derived purely
  // from seed_salt — same value every sample within a run, but
  // different between runs with different persona_seeds. Because each
  // sample gets the same bias factor, the integrated sum diverges
  // linearly with the bias, and different seeds produce visibly
  // different sums (∆sum ≈ |original sum| × bias_amplitude × seed_uniform).
  //
  // Amplitudes:
  //   kBiasAmplitude  = 1e-5  — ≈ -100 dB, below DAC dither, below
  //                              human perception even on headphones.
  //                              Sum-effect on a 124-magnitude integral
  //                              is ~6e-4 — comfortably above fpjs's
  //                              hash quantization.
  //   kNoiseAmplitude = 1e-7  — per-sample tremor; doesn't drive the
  //                              fingerprint divergence (because it
  //                              still integrates to 0), but ensures
  //                              individual sample bytes vary so
  //                              downstream byte-level hashes also
  //                              shift per seed.
  constexpr float kBiasAmplitude = 1e-5f;
  constexpr float kNoiseAmplitude = 1e-7f;

  // Per-seed uniform in [0, 1). Same value every sample → constant
  // multiplicative bias for the whole render → integrated sum becomes
  // a function of the persona seed.
  //
  // CAREFUL: raw seed_salt for small persona seeds (e.g.
  // --persona-seed=42 → salt=42) lives entirely in the bottom 8 bits.
  // A naive (salt >> 8) / 2^24 would collapse to 0, killing the bias.
  // Run the salt through the same xor-shift mix used by NoiseAt to
  // spread the entropy across all 32 bits first, THEN slice 24 bits.
  uint32_t mixed_salt = seed_salt;
  mixed_salt ^= mixed_salt >> 16;
  mixed_salt *= 0x85ebca6bu;
  mixed_salt ^= mixed_salt >> 13;
  const float seed_uniform =
      static_cast<float>(mixed_salt >> 8) / 16777216.0f;
  // Scale factor applied to every sample. 1.0 baseline + per-seed bias.
  const float seed_scale = 1.0f + seed_uniform * kBiasAmplitude;

  for (size_t i = 0; i < samples.size(); ++i) {
    // GLOBAL sample index keys the per-sample tremor across the entire
    // render — quantum boundaries don't reset it (which would let the
    // tremor pattern repeat every 128 samples and cancel mid-stream).
    const uint32_t h = NoiseAt(
        static_cast<uint32_t>(sample_offset + i), seed_salt);
    const float u = static_cast<float>(h >> 8) / 16777216.0f;
    const float per_sample = (u - 0.5f) * (2.0f * kNoiseAmplitude);
    // Multiplicative bias + additive tremor:
    //   |new| = |orig × seed_scale + per_sample|
    // For non-silent samples the bias dominates and the per-sample
    // term just dithers the LSB. For silence (sample=0), only the
    // per-sample tremor applies, which still touches the byte rep.
    samples[i] = samples[i] * seed_scale + per_sample;
  }
}

}  // namespace blink::fingerprinting
