# Patches

This fork's changes to upstream Chromium, split into one patch file per
feature/concern. Every upstream source file appears in **exactly one** patch,
so a Chromium version bump only conflicts in the patch(es) that touch the
changed files — not the whole tree.

Apply order is defined in [`series`](series). Order is cosmetic for `git apply`
(no two patches touch the same file), but the list reads top-down from
foundational plumbing to leaf features.

```sh
# apply everything, in order
while read p; do git apply "patches/$p"; done < patches/series
# or: ./patches/apply.sh
```

## Layout

| Patch | What it does |
|-------|--------------|
| `branding/branding.patch` | Product name, `Info.plist`, `BRANDING`, strings. |
| `branding/icons.patch` | Theme image assets (see **Binary assets** below). |
| `persona/persona-seed.patch` | `--persona-seed` switch + forwarding the seed to every renderer so the whole session derives one persona. |
| `persona/fingerprint-profile.patch` | The `blink::fingerprinting::Current()` profile (seed → persona) + its `BUILD.gn` wiring. The accessor the rest of the fingerprint patches read from. |
| `privacy/disable-intrusive-apis.patch` | Disables Topics, FLEDGE, WebUSB, and similar high-entropy / intrusive APIs by feature flag. |
| `fingerprint/navigator.patch` | `navigator.*` JS surface spoofing (UA, platform, hardwareConcurrency, deviceMemory, languages, installed apps, share API), runtime-enabled-features. |
| `fingerprint/display.patch` | Screen/window metrics, media queries, macOS scrollbar layout. |
| `fingerprint/device-sensors.patch` | Battery, NetInfo, media capabilities, speech voices, keyboard layout, WebGPU adapter, GPU data. |
| `fingerprint/timing-misc.patch` | Time clamper, rVFC cadence, `URL` parsing parity. |
| `fonts/lean-windows-fonts.patch` | Bundled metric-compatible font files (see **Binary assets**). |
| `fonts/font-substitution.patch` | Font fallback/allowlist + cache so the bundled set is what pages can enumerate. |
| `canvas-bridge/component.patch` | The canvas-bridge component + platform client/codec, build wiring, startup pre-warm. |
| `canvas-bridge/canvas2d.patch` | 2D canvas readback paths routed through the bridge. |
| `canvas-bridge/webgl.patch` | WebGL readback paths routed through the bridge. |
| `audio/webaudio.patch` | WebAudio rendering/destination handling for stable audio fingerprints. |
| `network/webrtc-leak-shield.patch` | Forces WebRTC off public UDP, RTCPeerConnection + mediaDevices hardening. |
| `network/tls-fingerprint.patch` | ClientHello shaping (drops the Chromium-150 Trust Anchor IDs extension) + net feature flags. |
| `devtools/humanized-input.patch` | Non-CDP humanized cursor/input over the custom DevTools protocol surface. |
| `ui/chrome-ui.patch` | Browser UI customizations (menus, toolbar, location bar, blank NTP, WebUI configs). |
| `ui/search-engines.patch` | Removes the default search provider / starter-pack engines. |

## Binary assets

`branding/icons.patch` and `fonts/lean-windows-fonts.patch` were generated
without `git diff --binary`, so they contain only `Binary files … differ`
markers, **not** the file bytes. They document *which* assets the fork
replaces/adds; they do not recreate them on apply. The actual icon and font
files are supplied separately (checked-in assets / build step), not by these
patches.

## Re-splitting

If the monolithic diff is ever regenerated, `tools/split_patch.py` (the script
that produced this tree) re-splits it and verifies a byte-exact round-trip.
