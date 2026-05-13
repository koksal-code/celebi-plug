"""Aircraft providers — OpenSky (default, anonymous tier) + ADS-B-lol.

Military and "special/blocked" aircraft are dropped at this layer; the
legal_guard module also re-filters every record before it leaves the API.
"""

from __future__ import annotations

import os
from typing import Any

from legal_guard import filter_records
from utils.http import HttpError, get_json

from .base import BaseProvider


# OpenSky "states/all" column order is positional. See:
# https://opensky-network.org/apidoc/rest.html#all-state-vectors
_OPENSKY_COLUMNS = [
    "icao24", "callsign", "origin_country", "time_position",
    "last_contact", "lon", "lat", "baro_altitude_m", "on_ground",
    "velocity_ms", "heading", "vertical_rate_ms", "sensors",
    "geo_altitude_m", "squawk", "spi", "position_source",
]


def _state_to_dict(state: list[Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for idx, key in enumerate(_OPENSKY_COLUMNS):
        record[key] = state[idx] if idx < len(state) else None
    callsign = record.get("callsign")
    record["callsign"] = (callsign or "").strip() or None
    velocity = record.get("velocity_ms")
    record["speed_kmh"] = round(velocity * 3.6, 1) if isinstance(velocity, (int, float)) else None
    return record


class OpenSkyProvider(BaseProvider):
    category = "aircraft"
    source_id = "opensky"

    STATES_URL = "https://opensky-network.org/api/states/all"

    def __init__(self) -> None:
        super().__init__()
        self.username = (os.environ.get("OPENSKY_USERNAME") or "").strip()
        self.password = (os.environ.get("OPENSKY_PASSWORD") or "").strip()

    def _auth_headers(self) -> dict[str, str] | None:
        if not self.username or not self.password:
            return None
        import base64
        creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}

    def by_callsign(self, callsign: str) -> dict[str, Any] | None:
        """Search the global states snapshot. Anonymous tier — slow but free."""
        target = (callsign or "").strip().upper()
        if not target:
            return None
        data = get_json(self.STATES_URL, headers=self._auth_headers(), timeout=12.0)
        for state in data.get("states") or []:
            rec = _state_to_dict(state)
            cs = (rec.get("callsign") or "").upper()
            if cs == target or cs.startswith(target):
                kept = filter_records("aircraft", [rec])
                return kept[0] if kept else None
        return None

    def nearby(self, lat: float, lon: float, *, radius_km: float = 50.0) -> list[dict[str, Any]]:
        # OpenSky has bbox params (lamin, lomin, lamax, lomax).
        # 1 deg lat ≈ 111 km — use cosine for lon.
        import math
        d_lat = radius_km / 111.0
        d_lon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
        params = {
            "lamin": lat - d_lat,
            "lomin": lon - d_lon,
            "lamax": lat + d_lat,
            "lomax": lon + d_lon,
        }
        data = get_json(self.STATES_URL, params=params, headers=self._auth_headers(), timeout=10.0)
        records = [_state_to_dict(s) for s in (data.get("states") or [])]
        return filter_records("aircraft", records)


class AdsbLolProvider(BaseProvider):
    """Free public ADS-B aggregator at https://api.adsb.lol/ — no token."""

    category = "aircraft"
    source_id = "adsb-lol"

    BASE = "https://api.adsb.lol/v2"

    def by_callsign(self, callsign: str) -> dict[str, Any] | None:
        try:
            data = get_json(f"{self.BASE}/callsign/{callsign.strip().upper()}", timeout=8.0)
        except HttpError:
            return None
        aircraft = (data.get("ac") or [])
        if not aircraft:
            return None
        kept = filter_records("aircraft", [self._normalize(aircraft[0])])
        return kept[0] if kept else None

    def nearby(self, lat: float, lon: float, *, radius_km: float = 50.0) -> list[dict[str, Any]]:
        # adsb.lol takes nautical miles in /point/lat/lon/distance
        radius_nm = max(1, int(round(radius_km * 0.539957)))
        try:
            data = get_json(f"{self.BASE}/point/{lat}/{lon}/{radius_nm}", timeout=8.0)
        except HttpError:
            return []
        records = [self._normalize(item) for item in (data.get("ac") or [])]
        return filter_records("aircraft", records)

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "icao24": item.get("hex"),
            "callsign": (item.get("flight") or "").strip() or None,
            "lat": item.get("lat"),
            "lon": item.get("lon"),
            "baro_altitude_m": (item.get("alt_baro") or 0) * 0.3048 if item.get("alt_baro") else None,
            "speed_kmh": round((item.get("gs") or 0) * 1.852, 1) if item.get("gs") else None,
            "heading": item.get("track"),
            "category": item.get("category"),
            "special": item.get("dbFlags"),  # raw flag — legal_guard re-checks
        }
