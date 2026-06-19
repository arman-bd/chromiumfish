"""Fetch several pages at once under one persona (async API)."""
import asyncio
from chromiumfish.async_api import AsyncChromiumfish

URLS = ["https://example.com", "https://example.org", "https://example.net"]


async def main():
    async with AsyncChromiumfish(persona_seed="delta-1") as browser:
        async def title(url):
            page = await browser.new_page()
            await page.goto(url)
            return url, await page.title()

        for url, name in await asyncio.gather(*(title(u) for u in URLS)):
            print(name, "<-", url)


asyncio.run(main())
