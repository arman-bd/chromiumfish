---
title: Personas
nav_order: 4
---

# Personas
{: .no_toc }

1. TOC
{:toc}

---

A **persona** is the complete, self-consistent fingerprint ChromiumFish presents:
user-agent, Client Hints, WebGL vendor/renderer, fonts, canvas/audio hashes, screen
metrics, and more. Every persona is derived deterministically from a single integer — the
**`persona_seed`**.

## The core idea

```
persona_seed ──▶ deterministic engine ──▶ one coherent fingerprint
```

- **Same seed → same persona.** Re-running with `persona_seed=27182` reproduces the exact
  same fingerprint every time — ideal for cross-session continuity (the site sees a
  returning user, not a new device each visit).
- **Different seed → uncorrelated persona.** Change the seed and every surface changes
  together, consistently. Two seeds don't share canvas/audio hashes, so sessions can't be
  linked through them.

### Python

```python
from chromiumfish.sync_api import Chromiumfish

# Account A — always this identity
with Chromiumfish(persona_seed=1001) as browser:
    ...

# Account B — a different, uncorrelated identity
with Chromiumfish(persona_seed=2002) as browser:
    ...
```

### Node

```javascript
const a = await ChromiumFish({ personaSeed: 1001 });
const b = await ChromiumFish({ personaSeed: 2002 });
```

## Choosing seeds

- **Pin a seed per account / per profile.** Store the mapping yourself (e.g.
  `account_id → seed`) so each identity is reproducible.
- **Rotate seeds for anonymity.** For one-off scrapes where you don't want any
  cross-session linkage, use a fresh random seed each run.
- **Keep network and persona aligned.** A persona's locale/timezone should match its exit
  IP — pair seeds with proxies deliberately.

{: .warning }
> A persona spoofs the **browser fingerprint**, not your network identity. IP reputation,
> TLS, and behaviour still matter. For high-friction targets, combine a persona with a
> clean residential proxy and human-like interaction.

## What's deterministic per seed

| Surface | Behaviour |
|---------|-----------|
| User-Agent + Client Hints | Coherent desktop persona, consistent across UA and high-entropy hints |
| WebGL vendor/renderer | Reports a real D3D11/ANGLE GPU string; no Apple/Metal leakage |
| Canvas / WebGL pixels | Per-seed deterministic isolation (bundled addon) |
| Audio | Per-seed deterministic offset, below perceptual threshold |
| Fonts | Windows font set present; host fonts hidden |
