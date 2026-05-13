"""Launch a GUI browser at the studio autopilot URL and wait for the MP4 to land.

Headed Chrome only — recording needs GPU/WebGL/MP4 (per AGENTS.md). This
module never tries to bypass that; it just orchestrates the existing
studio so the agent can deliver a finished .mp4 file instead of a URL.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Iterable


def _chrome_launch_command() -> list[str] | None:
    """Pick a way to open Chrome on the current OS."""
    if sys.platform == "darwin":
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "--user-data-dir=/tmp/celebi-plug-chrome-profile",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--autoplay-policy=no-user-gesture-required",
        ]
    if os.name == "nt":
        for path in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ):
            if Path(path).exists():
                return [path]
        return None
    for binary in ("google-chrome", "chromium", "chromium-browser"):
        if _which(binary):
            return [binary, "--autoplay-policy=no-user-gesture-required"]
    return None


def _which(cmd: str) -> str | None:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(d) / cmd
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def build_autopilot_url(
    base: str,
    *,
    place: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius: int | None = None,
    aspect: str = "16-9",
    preset: str = "showcase",
    poi: str = "skip",
    duration: int | None = None,
    narrate: str | None = None,
) -> str:
    params: list[tuple[str, str]] = []
    if place:
        params.append(("q", place))
    if lat is not None and lon is not None:
        params.append(("lat", str(lat)))
        params.append(("lon", str(lon)))
    if radius is not None:
        params.append(("radius", str(radius)))
    params.extend([("aspect", aspect), ("preset", preset), ("poi", poi), ("autostart", "1")])
    if duration is not None:
        params.append(("duration", str(duration)))
    if narrate:
        params.append(("narrate", narrate))
    return f"{base}?{urllib.parse.urlencode(params)}"


def launch_browser(url: str) -> bool:
    cmd = _chrome_launch_command()
    if cmd is None:
        return False
    try:
        subprocess.Popen(
            cmd + [url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, FileNotFoundError):
        return False
    return True


def watch_downloads(
    *,
    timeout_seconds: float = 120.0,
    poll_seconds: float = 1.5,
    glob: str = "celebi-plug-*.mp4",
    started_at: float | None = None,
    folders: Iterable[Path] | None = None,
) -> Path | None:
    """Wait for a fresh ``celebi-plug-*.mp4`` to appear in Downloads."""
    if folders is None:
        folders = [Path.home() / "Downloads"]
    started_at = started_at or time.time()
    deadline = started_at + timeout_seconds
    last_seen_size: dict[Path, int] = {}
    while time.time() < deadline:
        for folder in folders:
            if not folder.exists():
                continue
            for candidate in folder.glob(glob):
                try:
                    stat = candidate.stat()
                except OSError:
                    continue
                if stat.st_mtime < started_at - 2:
                    continue
                # ensure the file has finished writing (size stable across 2 polls)
                prior = last_seen_size.get(candidate)
                last_seen_size[candidate] = stat.st_size
                if prior is not None and prior == stat.st_size and stat.st_size > 0:
                    return candidate
        time.sleep(poll_seconds)
    return None
