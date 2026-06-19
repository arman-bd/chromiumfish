"""Print what a page sees for two seeds — same persona, different per-seed entropy."""
from chromiumfish.sync_api import Chromiumfish

PROBE = """() => ({
  userAgent: navigator.userAgent,
  platform: navigator.platform,
  languages: navigator.languages.join(','),
  cores: navigator.hardwareConcurrency,
  memoryGB: navigator.deviceMemory,
  screen: screen.width + 'x' + screen.height,
})"""

for seed in ("alpha-7", "bravo-3"):
    with Chromiumfish(persona_seed=seed) as browser:
        page = browser.new_page()
        page.goto("https://example.com")
        fingerprint = page.evaluate(PROBE)

    print(f"\n[{seed}]")
    for key, value in fingerprint.items():
        print(f"  {key} = {value}")
