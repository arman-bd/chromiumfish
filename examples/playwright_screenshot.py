"""Save a full-page screenshot under a seeded persona."""
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="charlie-9", window_size=(1280, 900)) as browser:
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("https://example.com/", wait_until="load")
    page.screenshot(path="screenshot.png", full_page=True)
    print("saved screenshot.png —", page.title())
