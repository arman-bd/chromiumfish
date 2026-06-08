"""Download, verify, and cache the ChromiumFish browser build.

Fetch model: resolve ``version × platform`` to a GitHub
Release asset, verify its SHA-256, extract it to a per-version cache dir, and
return the path to the launchable binary.
"""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from .version import browser_version, release_base_url


class UnsupportedPlatformError(RuntimeError):
    pass


def cache_root() -> Path:
    env = os.environ.get("CHROMIUMFISH_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "chromiumfish"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "chromiumfish"
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "chromiumfish"


def platform_slug() -> str:
    """e.g. ``linux-x64``, ``win-x64``, ``mac-arm64``."""
    machine = platform.machine().lower()
    arch = {
        "x86_64": "x64", "amd64": "x64",
        "aarch64": "arm64", "arm64": "arm64",
    }.get(machine)
    if arch is None:
        raise UnsupportedPlatformError(f"unsupported architecture: {machine}")
    if sys.platform.startswith("linux"):
        return f"linux-{arch}"
    if sys.platform == "darwin":
        return f"mac-{arch}"
    if os.name == "nt":
        return f"win-{arch}"
    raise UnsupportedPlatformError(f"unsupported platform: {sys.platform}")


def _asset_name(version: str) -> str:
    slug = platform_slug()
    ext = "zip" if slug.startswith("win") else "tar.gz"
    return f"chromiumfish-{version}-{slug}.{ext}"


def _binary_name() -> str:
    if os.name == "nt":
        return "chromiumfish.exe"
    return "chromiumfish"  # falls back to "chrome" during discovery


def install_dir(version: str | None = None) -> Path:
    version = version or browser_version()
    return cache_root() / version / platform_slug()


def find_binary(root: Path) -> Path | None:
    """Locate the launchable binary inside an extracted build."""
    candidates = ["chromiumfish", "chrome", "chromiumfish.exe", "chrome.exe", "ChromiumFish"]
    for name in candidates:
        direct = root / name
        if direct.is_file():
            return direct
    for name in candidates:
        for hit in root.rglob(name):
            if hit.is_file():
                return hit
    return None


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[chromiumfish] downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as out:  # noqa: S310
        total = int(resp.headers.get("Content-Length", 0))
        read = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            read += len(chunk)
            if total:
                pct = read * 100 // total
                print(f"\r[chromiumfish] {pct:3d}%  ({read >> 20} / {total >> 20} MiB)",
                      end="", file=sys.stderr)
        print("", file=sys.stderr)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _verify(archive: Path, base_url: str, asset: str) -> None:
    try:
        with urllib.request.urlopen(f"{base_url}/{asset}.sha256") as r:  # noqa: S310
            expected = r.read().decode().split()[0].strip()
    except Exception:  # noqa: BLE001
        print("[chromiumfish] warning: no .sha256 published, skipping verification", file=sys.stderr)
        return
    actual = _sha256(archive)
    if actual != expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {asset}: {actual} != {expected}")


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest)  # noqa: S202 - trusted first-party asset


def _macos_prepare(target: Path) -> None:
    """Identity-clean macOS prep.

    1. Strip the ``com.apple.quarantine`` flag. Programmatic downloads usually
       don't set it, but browsers/tools might — removing it avoids Gatekeeper's
       "unidentified developer" block without any notarization.
    2. Ensure the bundle is ad-hoc signed (``codesign -s -``). Apple Silicon
       refuses to run an unsigned binary; ad-hoc signing fixes that and embeds
       NO certificate, name, or identity. (Release builds ship ad-hoc signed;
       this is a defensive fallback.)
    """
    if sys.platform != "darwin":
        return
    app = next(target.glob("*.app"), None)
    sign_target = app or find_binary(target)
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(target)],
                   check=False, capture_output=True)
    if sign_target:
        valid = subprocess.run(["codesign", "--verify", "--quiet", str(sign_target)],
                               capture_output=True).returncode == 0
        if not valid:
            subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(sign_target)],
                           check=False, capture_output=True)


def fetch(version: str | None = None, *, force: bool = False) -> Path:
    """Ensure the browser build is present and return the binary path."""
    version = version or browser_version()
    target = install_dir(version)

    if force and target.exists():
        shutil.rmtree(target, ignore_errors=True)

    if target.exists():
        binp = find_binary(target)
        if binp:
            return binp

    base = release_base_url(version)
    asset = _asset_name(version)
    archive = cache_root() / version / asset
    _download(f"{base}/{asset}", archive)
    _verify(archive, base, asset)
    _extract(archive, target)
    archive.unlink(missing_ok=True)
    _macos_prepare(target)

    binp = find_binary(target)
    if not binp:
        raise RuntimeError(f"no browser binary found in extracted build at {target}")
    if os.name != "nt":
        binp.chmod(0o755)
    print(f"[chromiumfish] ready: {binp}", file=sys.stderr)
    return binp


def binary_path(version: str | None = None, *, download: bool = True) -> Path:
    """Path to the cached binary, fetching it if needed (and allowed)."""
    version = version or browser_version()
    existing = find_binary(install_dir(version))
    if existing:
        return existing
    if not download:
        raise FileNotFoundError(
            f"ChromiumFish {version} not installed. Run `chromiumfish fetch`."
        )
    return fetch(version)
