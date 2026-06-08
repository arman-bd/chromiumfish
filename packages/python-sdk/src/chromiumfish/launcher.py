"""Shared launch-argument construction for the sync/async wrappers."""
from __future__ import annotations

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


def launch_options(
    *,
    executable_path: Path,
    headless: bool,
    persona_seed: int | None,
    proxy: dict[str, Any] | None,
    window_size: tuple[int, int] | None,
    args: list[str] | None,
    extra: dict[str, Any],
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
    return opts
