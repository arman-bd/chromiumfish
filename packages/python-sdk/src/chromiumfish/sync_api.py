"""Sync Playwright wrapper for ChromiumFish.

    from chromiumfish.sync_api import Chromiumfish

    with Chromiumfish(persona_seed="alpha-7", headless=True) as browser:
        page = browser.new_page()
        page.goto("https://example.com")
"""
from __future__ import annotations

from typing import Any

from playwright.sync_api import Browser, sync_playwright

from .fetch import binary_path
from .launcher import launch_options, resolve_timezone


class Chromiumfish:
    def __init__(
        self,
        *,
        persona_seed: str | None = None,
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

    def start(self) -> Browser:
        exe = binary_path(self._version, download=self._download)
        tz = resolve_timezone(
            self._timezone, proxy=self._opts["proxy"], download=self._download
        )
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            **launch_options(executable_path=exe, tz=tz, **self._opts)
        )
        return self._browser

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._pw:
            self._pw.stop()
            self._pw = None

    def __enter__(self) -> Browser:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()
