"""Wildfire module — NASA FIRMS feed, optional bbox."""

from __future__ import annotations

from typing import Any

from providers.wildfire import NasaFirmsProvider
from utils.geocode import GeocodeError, geocode


def active(
    *,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 500,
    min_confidence: int = 30,
) -> list[dict[str, Any]]:
    return NasaFirmsProvider().active(bbox=bbox, limit=limit, min_confidence=min_confidence)


def active_near(place: str, *, radius_km: float = 200.0, limit: int = 500) -> dict[str, Any]:
    try:
        geo = geocode(place)
    except GeocodeError as exc:
        raise ValueError(str(exc)) from exc
    import math

    d_lat = radius_km / 111.0
    d_lon = radius_km / (111.0 * max(math.cos(math.radians(geo["lat"])), 0.1))
    bbox = (geo["lon"] - d_lon, geo["lat"] - d_lat, geo["lon"] + d_lon, geo["lat"] + d_lat)
    fires = active(bbox=bbox, limit=limit)
    return {
        "place": geo["name"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "radius_km": radius_km,
        "fires": fires,
    }
