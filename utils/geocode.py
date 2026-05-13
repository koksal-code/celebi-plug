"""Token-free geocoding via OpenStreetMap Nominatim.

If the user sets ``CELEBI_GEOCODER=mapbox`` and a Mapbox public token is
available, we route through the Mapbox geocoder instead — same return
shape, better precision in some regions.
"""

from __future__ import annotations

import os
from typing import Optional

from .http import HttpError, get_json


class GeocodeError(RuntimeError):
    pass


def _provider() -> str:
    raw = (os.environ.get("CELEBI_GEOCODER") or "osm").strip().lower()
    return "mapbox" if raw == "mapbox" else "osm"


def _mapbox_token() -> Optional[str]:
    token = (os.environ.get("MAPBOX_TOKEN") or "").strip().strip('"').strip("'")
    return token if token.startswith("pk.") else None


def geocode(place: str) -> dict:
    """Resolve a place name to {name, lat, lon, bbox, source}."""
    place = (place or "").strip()
    if not place:
        raise GeocodeError("empty place name")
    if _provider() == "mapbox":
        token = _mapbox_token()
        if token:
            try:
                return _geocode_mapbox(place, token)
            except (HttpError, GeocodeError):
                pass  # fall through to OSM
    try:
        return _geocode_osm(place)
    except HttpError as exc:
        raise GeocodeError(f"geocoding unavailable: {exc}") from exc


def _geocode_osm(place: str) -> dict:
    data = get_json(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1, "addressdetails": 0},
        headers={"Accept-Language": "en"},
        timeout=6.0,
    )
    if not data:
        raise GeocodeError(f"no result for '{place}'")
    first = data[0]
    try:
        lat = float(first["lat"])
        lon = float(first["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodeError("malformed nominatim result") from exc
    bbox = None
    bb = first.get("boundingbox")
    if isinstance(bb, list) and len(bb) == 4:
        try:
            south, north, west, east = (float(v) for v in bb)
            bbox = [west, south, east, north]
        except ValueError:
            bbox = None
    return {
        "name": first.get("display_name") or place,
        "lat": lat,
        "lon": lon,
        "bbox": bbox,
        "source": "osm-nominatim",
    }


def _geocode_mapbox(place: str, token: str) -> dict:
    import urllib.parse as _p

    encoded = _p.quote(place, safe="")
    data = get_json(
        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded}.json",
        params={"access_token": token, "limit": 1},
        timeout=6.0,
    )
    feats = data.get("features") or []
    if not feats:
        raise GeocodeError(f"no result for '{place}'")
    feat = feats[0]
    center = feat.get("center") or []
    if len(center) != 2:
        raise GeocodeError("malformed mapbox result")
    lon, lat = float(center[0]), float(center[1])
    bbox = feat.get("bbox")
    return {
        "name": feat.get("place_name") or place,
        "lat": lat,
        "lon": lon,
        "bbox": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
        "source": "mapbox-geocoder",
    }
