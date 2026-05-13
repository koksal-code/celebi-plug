"""Weather module — picks provider by env, geocodes city if needed."""

from __future__ import annotations

import os
from typing import Any

from providers.weather import OpenMeteoProvider, OpenWeatherProvider
from utils.geocode import GeocodeError, geocode


def _provider_name() -> str:
    return (os.environ.get("CELEBI_WEATHER_PROVIDER") or "open-meteo").strip().lower()


def _make_provider():
    name = _provider_name()
    if name == "openweather":
        ow = OpenWeatherProvider()
        if ow.is_available():
            return ow
    return OpenMeteoProvider()


def by_coords(lat: float, lon: float, *, marine: bool = False) -> dict[str, Any]:
    provider = _make_provider()
    payload = provider.current(lat, lon)
    if marine:
        marine_info = provider.marine(lat, lon)
        if marine_info is None and isinstance(provider, OpenWeatherProvider):
            # Marine fallback always uses Open-Meteo.
            marine_info = OpenMeteoProvider().marine(lat, lon)
        if marine_info is not None:
            payload["marine"] = marine_info
    return payload


def by_city(place: str, *, marine: bool = False) -> dict[str, Any]:
    try:
        geo = geocode(place)
    except GeocodeError as exc:
        raise ValueError(str(exc)) from exc
    result = by_coords(geo["lat"], geo["lon"], marine=marine)
    result["place"] = geo["name"]
    result["geocoder"] = geo["source"]
    return result
