#!/usr/bin/env python3
"""Playwright quickstart: open a page through a seeded ChromiumFish persona."""
from chromiumfish.sync_api import Chromiumfish

with Chromiumfish(persona_seed="alpha-7") as browser:
    page = browser.new_page()
    page.goto("https://example.com/")
    print("title:", page.title())
    print("url:  ", page.url)
