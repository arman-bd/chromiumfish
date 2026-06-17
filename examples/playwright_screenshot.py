#!/usr/bin/env python3
"""Save a full-page screenshot of a real site through a seeded persona."""
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="charlie-9", window_size=(1280, 900)) as browser:
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("https://news.ycombinator.com/", wait_until="load")
    page.screenshot(path="hn.png", full_page=True)
    print("saved hn.png —", page.title())
