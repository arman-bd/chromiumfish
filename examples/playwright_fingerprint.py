#!/usr/bin/env python3
"""What a page sees per seed: a consistent Windows persona; deviceMemory varies."""
from chromiumfish.sync_api import Chromiumfish

PROBE = """() => ({
  userAgent: navigator.userAgent,
  platform:  navigator.platform,
  languages: navigator.languages.join(','),
  cores:     navigator.hardwareConcurrency,
  memoryGB:  navigator.deviceMemory,
  screen:    screen.width + 'x' + screen.height,
})"""

for seed in ("alpha-7", "bravo-3"):
    with Chromiumfish(persona_seed=seed) as browser:
        page = browser.new_page()
        page.goto("https://example.com")
        fp = page.evaluate(PROBE)
    print(f"\n[seed={seed}]")
    for key, value in fp.items():
        tag = "  <- varies per seed" if key == "memoryGB" else ""
        print(f"  {key:9} = {value}{tag}")
