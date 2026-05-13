"""Aircraft module — OpenSky default, ADS-B-lol fallback."""

from __future__ import annotations

import os
from typing import Any

from providers.aircraft import AdsbLolProvider, OpenSkyProvider
from utils.geocode import GeocodeError, geocode


def _provider_name() -> str:
    return (os.environ.get("CELEBI_AIRCRAFT_PROVIDER") or "opensky").strip().lower()


def _providers():
    name = _provider_name()
    primary = OpenSkyProvider() if name == "opensky" else AdsbLolProvider()
    fallback = AdsbLolProvider() if name == "opensky" else OpenSkyProvider()
    return primary, fallback


def by_callsign(callsign: str) -> dict[str, Any] | None:
    primary, fallback = _providers()
    try:
        record = primary.by_callsign(callsign)
        if record:
            return record
    except Exception:  # noqa: BLE001
        record = None
    try:
        return fallback.by_callsign(callsign)
    except Exception:  # noqa: BLE001
        return None


def near_coords(lat: float, lon: float, *, radius_km: float = 50.0) -> list[dict[str, Any]]:
    primary, fallback = _providers()
    try:
        results = primary.nearby(lat, lon, radius_km=radius_km)
        if results:
            return results
    except Exception:  # noqa: BLE001
        results = []
    try:
        return fallback.nearby(lat, lon, radius_km=radius_km)
    except Exception:  # noqa: BLE001
        return results


def near_place(place: str, *, radius_km: float = 50.0) -> dict[str, Any]:
    try:
        geo = geocode(place)
    except GeocodeError as exc:
        raise ValueError(str(exc)) from exc
    aircraft = near_coords(geo["lat"], geo["lon"], radius_km=radius_km)
    return {
        "place": geo["name"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "radius_km": radius_km,
        "aircraft": aircraft,
    }
