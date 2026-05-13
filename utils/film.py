"""Launch a GUI browser at the studio autopilot URL and wait for the MP4 to land.

Headed Chrome only — recording needs GPU/WebGL/MP4 (per AGENTS.md). This
module never tries to bypass that; it just orchestrates the existing
studio so the agent can deliver a finished .mp4 file instead of a URL.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable


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


def extract_center_from_geojson(path: str | Path) -> tuple[float, float] | None:
    """Return the (lat, lon) centroid of all coordinates in a GeoJSON file.

    Supports FeatureCollection, Feature, and all geometry types. Returns
    ``None`` if the file cannot be read or contains no coordinates.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        coords = _collect_geojson_coords(data)
        if not coords:
            return None
        lats = [c[1] for c in coords]
        lons = [c[0] for c in coords]
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    except Exception:  # noqa: BLE001
        return None


def _collect_geojson_coords(obj: Any) -> list[list[float]]:
    if not isinstance(obj, dict):
        return []
    t = obj.get("type")
    if t == "FeatureCollection":
        out: list[list[float]] = []
        for f in obj.get("features") or []:
            out.extend(_collect_geojson_coords(f))
        return out
    if t == "Feature":
        return _collect_geojson_coords(obj.get("geometry") or {})
    if t == "Point":
        c = obj.get("coordinates")
        return [c] if isinstance(c, list) and len(c) >= 2 else []
    if t in ("LineString", "MultiPoint"):
        return [c for c in (obj.get("coordinates") or []) if isinstance(c, list) and len(c) >= 2]
    if t in ("Polygon", "MultiLineString"):
        out = []
        for ring in obj.get("coordinates") or []:
            out.extend(c for c in ring if isinstance(c, list) and len(c) >= 2)
        return out
    if t == "MultiPolygon":
        out = []
        for poly in obj.get("coordinates") or []:
            for ring in poly:
                out.extend(c for c in ring if isinstance(c, list) and len(c) >= 2)
        return out
    if t == "GeometryCollection":
        out = []
        for g in obj.get("geometries") or []:
            out.extend(_collect_geojson_coords(g))
        return out
    return []


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
