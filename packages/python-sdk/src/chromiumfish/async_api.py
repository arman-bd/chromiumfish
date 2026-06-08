"""Async Playwright wrapper for ChromiumFish.

    from chromiumfish.async_api import AsyncChromiumfish

    async with AsyncChromiumfish(persona_seed=27182, headless=True) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com")
"""
from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Browser, async_playwright

from .fetch import binary_path
from .launcher import launch_options, resolve_timezone


class AsyncChromiumfish:
    def __init__(
        self,
        *,
        persona_seed: int | None = None,
        headless: bool = True,
        proxy: dict[str, Any] | None = None,
        window_size: tuple[int, int] | None = (1920, 1080),
        version: str | None = None,
        download: bool = True,
        timezone: str | None = None,
        args: list[str] | None = None,
        **launch_kwargs: Any,
    ) -> None:
        self._opts = dict(
            persona_seed=persona_seed,
            headless=headless,
            proxy=proxy,
            window_size=window_size,
            args=args,
            extra=launch_kwargs,
        )
        self._version = version
        self._download = download
        # "auto" -> resolve from egress IP via the ip2tz DB; an IANA string is
        # used verbatim; None disables timezone handling.
        self._timezone = timezone
        self._pw = None
        self._browser: Browser | None = None

    async def start(self) -> Browser:
        exe = binary_path(self._version, download=self._download)
        # resolve_timezone may block on a network probe + DB download; keep it
        # off the event loop.
        tz = await asyncio.to_thread(
            resolve_timezone, self._timezone,
            proxy=self._opts["proxy"], download=self._download,
        )
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            **launch_options(executable_path=exe, tz=tz, **self._opts)
        )
        return self._browser

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    async def __aenter__(self) -> Browser:
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
