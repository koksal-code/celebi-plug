"""Tek-kare snapshot downloader.

Downloads a remote URL to a temp file and returns the Path. Used by the
CLI/API to produce a one-frame PNG/JPEG that the agent can hand to the
user — typical sources are the Mapbox Static Images endpoint and direct
JPEG snapshot URLs for public cameras (when registered).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .http import HttpError, get_bytes


_DEFAULT_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def download(url: str, *, dest: Path | None = None, timeout: float = 20.0) -> Path | None:
    """Fetch ``url`` and write the bytes to ``dest`` (or a fresh tmp file).

    Returns the path on success, ``None`` if the upstream refuses or the
    URL is not HTTP(S). Safe to call inline — never raises on network.
    """
    if not url or not url.lower().startswith(("http://", "https://")):
        return None
    try:
        data = get_bytes(url, timeout=timeout)
    except HttpError:
        return None
    if not data:
        return None
    suffix = _guess_suffix(url)
    if dest is None:
        fd, name = tempfile.mkstemp(prefix="celebi-snapshot-", suffix=suffix)
        os.close(fd)
        dest = Path(name)
    dest.write_bytes(data)
    return dest


def _guess_suffix(url: str) -> str:
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return ".jpg"
    if lower.endswith(".webp"):
        return ".webp"
    return ".png"


def open_in_browser(url: str) -> bool:
    """Open ``url`` in the user's default browser (best-effort)."""
    if not url:
        return False
    import subprocess
    import sys

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        return False
    return True
