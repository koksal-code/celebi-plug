"""Public cameras module — geocodes a place and lists nearby cameras."""

from __future__ import annotations

from typing import Any

from providers.cameras import OfficialCamerasProvider
from utils.geocode import GeocodeError, geocode


def near_place(place: str, *, radius_km: float = 50.0) -> dict[str, Any]:
    try:
        geo = geocode(place)
    except GeocodeError as exc:
        raise ValueError(str(exc)) from exc
    cams = OfficialCamerasProvider().near(geo["lat"], geo["lon"], radius_km=radius_km)
    return {
        "place": geo["name"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "radius_km": radius_km,
        "cameras": cams,
    }


def near_coords(lat: float, lon: float, *, radius_km: float = 50.0) -> list[dict[str, Any]]:
    return OfficialCamerasProvider().near(lat, lon, radius_km=radius_km)
