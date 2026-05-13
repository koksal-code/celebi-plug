"""Static map image URL builder.

Mapbox Static Images API when ``MAPBOX_TOKEN`` (pk.*) is available — same
public token the studio already uses, so no extra setup. Falls back to an
OpenStreetMap web link when the token is missing (no still image, but a
clickable map pin).

CelebiPlug style: satellite-streets-v12, orange pin (#f74e4e), retina
output, 720x480 by default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _mapbox_token() -> Optional[str]:
    token = (os.environ.get("MAPBOX_TOKEN") or "").strip().strip('"').strip("'")
    if token.startswith("pk."):
        return token
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        try:
            for raw in env.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line.startswith("MAPBOX_TOKEN="):
                    continue
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value.startswith("pk."):
                    return value
        except OSError:
            return None
    return None


def static_image(
    lat: float,
    lon: float,
    *,
    zoom: int = 13,
    width: int = 720,
    height: int = 480,
    marker: bool = True,
    style: str = "satellite-streets-v12",
    bearing: float | None = None,
    pitch: float | None = None,
) -> dict:
    """Return ``{"provider", "url", "is_image"}`` describing a static frame.

    ``is_image`` is True only when the URL resolves to an actual PNG/JPEG
    (i.e. Mapbox token available). When False, the URL is a web map link
    suitable for "click here to see live position".
    """
    width = max(64, min(width, 1280))
    height = max(64, min(height, 1280))
    zoom = max(0, min(zoom, 20))
    token = _mapbox_token()
    if token:
        marker_part = f"pin-l+f74e4e({lon},{lat})/" if marker else ""
        camera = f"{lon},{lat},{zoom}"
        if bearing is not None or pitch is not None:
            camera += f",{bearing or 0},{pitch or 0}"
        url = (
            f"https://api.mapbox.com/styles/v1/mapbox/{style}/static/"
            f"{marker_part}{camera}/{width}x{height}@2x"
            f"?access_token={token}"
        )
        return {"provider": "mapbox-static", "url": url, "is_image": True}
    return {
        "provider": "osm-page",
        "url": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map={zoom}/{lat}/{lon}",
        "is_image": False,
    }


def web_link(lat: float, lon: float, *, zoom: int = 15) -> str:
    """Always-available OSM page link, regardless of Mapbox token."""
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map={zoom}/{lat}/{lon}"
