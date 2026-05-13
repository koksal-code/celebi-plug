"""Weather providers — Open-Meteo (default, token-free) + OpenWeather."""

from __future__ import annotations

import os
from typing import Any

from utils.http import HttpError, get_json

from .base import BaseProvider


def _knots_to_kmh(value: float) -> float:
    return round(value * 1.852, 1)


class OpenMeteoProvider(BaseProvider):
    category = "weather"
    source_id = "open-meteo"

    BASE = "https://api.open-meteo.com/v1/forecast"
    MARINE = "https://marine-api.open-meteo.com/v1/marine"

    def current(self, lat: float, lon: float) -> dict[str, Any]:
        data = get_json(
            self.BASE,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                            "precipitation,wind_speed_10m,wind_direction_10m,weather_code",
                "wind_speed_unit": "kmh",
                "timezone": "auto",
            },
            timeout=6.0,
        )
        cur = data.get("current") or {}
        return {
            "source": self.source_id,
            "lat": lat,
            "lon": lon,
            "timezone": data.get("timezone"),
            "temperature_c": cur.get("temperature_2m"),
            "apparent_c": cur.get("apparent_temperature"),
            "humidity_pct": cur.get("relative_humidity_2m"),
            "precipitation_mm": cur.get("precipitation"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "wind_direction": cur.get("wind_direction_10m"),
            "weather_code": cur.get("weather_code"),
            "observed_at": cur.get("time"),
        }

    def marine(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Sea suitability. Returns None for inland points (404)."""
        try:
            data = get_json(
                self.MARINE,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "wave_height,wave_period,wave_direction",
                    "timezone": "auto",
                },
                timeout=6.0,
            )
        except HttpError:
            return None
        cur = data.get("current") or {}
        wave_h = cur.get("wave_height")
        if wave_h is None:
            return None
        suitable = wave_h is not None and wave_h <= 1.0
        return {
            "wave_height_m": wave_h,
            "wave_period_s": cur.get("wave_period"),
            "wave_direction": cur.get("wave_direction"),
            "sea_suitable": suitable,
        }


class OpenWeatherProvider(BaseProvider):
    category = "weather"
    source_id = "openweather"

    BASE = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = (api_key or os.environ.get("OPENWEATHER_API_KEY") or "").strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def current(self, lat: float, lon: float) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENWEATHER_API_KEY required")
        data = get_json(
            self.BASE,
            params={
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric",
            },
            timeout=6.0,
        )
        wind = data.get("wind") or {}
        main = data.get("main") or {}
        rain = data.get("rain") or {}
        return {
            "source": self.source_id,
            "lat": lat,
            "lon": lon,
            "temperature_c": main.get("temp"),
            "apparent_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "precipitation_mm": rain.get("1h"),
            "wind_kmh": _knots_to_kmh((wind.get("speed") or 0.0) * 1.94384),
            "wind_direction": wind.get("deg"),
            "weather_code": (data.get("weather") or [{}])[0].get("id"),
            "observed_at": data.get("dt"),
        }

    def marine(self, lat: float, lon: float):  # noqa: ARG002
        # OWM does not expose marine on the free tier; defer to Open-Meteo.
        return None
