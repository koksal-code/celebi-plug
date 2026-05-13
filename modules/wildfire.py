"""Wildfire module — NASA FIRMS feed, optional bbox."""

from __future__ import annotations

import math
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


def nearest_hotspot(place: str, *, search_radius_km: float = 500.0) -> dict[str, Any] | None:
    """Return the single highest-confidence active fire pixel nearest to *place*.

    Returns ``None`` when no fires are detected within *search_radius_km*.
    The returned dict includes lat/lon plus NASA FIRMS metadata so the caller
    can film it directly or build an info card.
    """
    try:
        bundle = active_near(place, radius_km=search_radius_km, limit=300)
    except ValueError:
        return None
    fires = bundle.get("fires") or []
    if not fires:
        return None
    center_lat, center_lon = bundle["lat"], bundle["lon"]

    def _dist_km(f: dict[str, Any]) -> float:
        dlat = math.radians(f["lat"] - center_lat)
        dlon = math.radians(f["lon"] - center_lon)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(center_lat))
            * math.cos(math.radians(f["lat"]))
            * math.sin(dlon / 2) ** 2
        )
        return 2 * 6371.0 * math.asin(math.sqrt(max(0.0, a)))

    # highest confidence first, then closest
    fires.sort(key=lambda f: (-float(f.get("confidence") or 0), _dist_km(f)))
    best = fires[0]
    dist = round(_dist_km(best), 1)
    return {
        "lat": best["lat"],
        "lon": best["lon"],
        "confidence": best.get("confidence"),
        "frp": best.get("frp"),
        "brightness": best.get("brightness"),
        "acquired_at": best.get("acquired_at"),
        "satellite": best.get("satellite"),
        "place": bundle["place"],
        "total_fires": len(fires),
        "distance_from_center_km": dist,
    }
