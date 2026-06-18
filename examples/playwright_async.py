#!/usr/bin/env python3
"""Async API: fetch several pages concurrently under one seeded persona."""
import asyncio

from chromiumfish.async_api import AsyncChromiumfish

URLS = [
    "https://example.com",
    "https://example.org",
    "https://example.net",
]


async def main() -> None:
    async with AsyncChromiumfish(persona_seed="delta-1") as browser:
        async def fetch_title(url: str) -> tuple[str, str]:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            return url, await page.title()

        for url, title in await asyncio.gather(*(fetch_title(u) for u in URLS)):
            print(f"{title!r:45}  <-  {url}")


if __name__ == "__main__":
    asyncio.run(main())
