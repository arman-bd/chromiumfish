"""Shared launch-argument construction for the sync/async wrappers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Flags that keep the GPU-less / SwiftShader path working and the persona
# engine happy. Mirrors the production launch_lean.sh defaults (minus anything
# that is now baked into the build / bundled addon).
BASE_ARGS: list[str] = [
    "--no-sandbox",
    "--no-zygote",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
]


def build_args(
    *,
    persona_seed: int | None = None,
    window_size: tuple[int, int] | None = (1920, 1080),
    extra_args: list[str] | None = None,
) -> list[str]:
    args = list(BASE_ARGS)
    if persona_seed is not None:
        args.append(f"--persona-seed={persona_seed}")
    if window_size is not None:
        args.append(f"--window-size={window_size[0]},{window_size[1]}")
    if extra_args:
        args.extend(extra_args)
    return args


def proxy_to_url(proxy: dict[str, Any] | None) -> str | None:
    """Flatten a Playwright proxy dict into a ``scheme://user:pass@host:port``
    URL for the egress probe. Returns None when no usable server is set."""
    if not proxy or not proxy.get("server"):
        return None
    server = proxy["server"]
    user, pwd = proxy.get("username"), proxy.get("password")
    if user and "://" in server:
        scheme, host = server.split("://", 1)
        return f"{scheme}://{user}:{pwd or ''}@{host}"
    return server


def resolve_timezone(
    timezone: str | None,
    *,
    proxy: dict[str, Any] | None,
    download: bool,
) -> str | None:
    """Interpret the wrapper's ``timezone`` option into a concrete IANA zone.

    * None       -> no timezone handling (returns None)
    * "auto"     -> probe the egress IP (through ``proxy``) and resolve it
                    against the downloadable ip2tz DB
    * "<IANA>"   -> used verbatim (no probe, no DB)
    """
    if not timezone:
        return None
    if timezone != "auto":
        return timezone
    from .ip2tz import resolve_timezone as _resolve  # lazy: avoids DB import cost
    return _resolve(proxy=proxy_to_url(proxy), download=download)


def launch_options(
    *,
    executable_path: Path,
    headless: bool,
    persona_seed: int | None,
    proxy: dict[str, Any] | None,
    window_size: tuple[int, int] | None,
    args: list[str] | None,
    extra: dict[str, Any],
    tz: str | None = None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "executable_path": str(executable_path),
        "headless": headless,
        "args": build_args(
            persona_seed=persona_seed, window_size=window_size, extra_args=args
        ),
    }
    if proxy is not None:
        opts["proxy"] = proxy
    opts.update(extra)
    if tz:
        # Chromium's ICU adopts TZ at process init — same mechanism the
        # production launch_lean.sh uses as the timezone source of truth.
        # Playwright's `env` replaces (not merges) the child environment, so
        # start from the current one. Our resolved TZ wins over any inherited.
        env = dict(os.environ)
        env.update(opts.get("env") or {})
        env["TZ"] = tz
        opts["env"] = env
    return opts
