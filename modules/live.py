"""Combined live view — used by ``celebi live <place>`` and ``/api/live``.

Bundles weather + nearby cameras + 24h wildfire/earthquake counts + a
Mapbox satellite still of the location into a single payload the agent
can summarise in one short paragraph.
"""

from __future__ import annotations

from typing import Any

from utils.geocode import GeocodeError, geocode
from utils.staticmap import static_image, web_link

from . import cameras as cameras_mod
from . import earthquake as earthquake_mod
from . import weather as weather_mod
from . import wildfire as wildfire_mod


def snapshot(place: str, *, marine: bool = False, radius_km: float = 50.0) -> dict[str, Any]:
    try:
        geo = geocode(place)
    except GeocodeError as exc:
        raise ValueError(str(exc)) from exc

    lat, lon = geo["lat"], geo["lon"]

    # Weather is cheap, always include.
    try:
        weather = weather_mod.by_coords(lat, lon, marine=marine)
    except Exception:  # noqa: BLE001
        weather = None

    # Cameras (public registry only).
    cams = cameras_mod.near_coords(lat, lon, radius_km=radius_km)

    # Wildfire / earthquake counts — short, not full payload.
    try:
        wildfires = wildfire_mod.active_near(place, radius_km=200.0, limit=200).get("fires", [])
    except Exception:  # noqa: BLE001
        wildfires = []
    try:
        quakes_24h = [
            q for q in earthquake_mod.recent(limit=200, min_magnitude=2.0)
            if _within(q.get("lat"), q.get("lon"), lat, lon, 300.0)
        ]
    except Exception:  # noqa: BLE001
        quakes_24h = []

    map_frame = static_image(lat, lon, zoom=12, width=720, height=480)

    return {
        "place": geo["name"],
        "lat": lat,
        "lon": lon,
        "weather": weather,
        "cameras": cams,
        "wildfires_nearby": len(wildfires),
        "earthquakes_nearby": len(quakes_24h),
        "map": map_frame,
        "web_link": web_link(lat, lon),
    }


def _within(a_lat, a_lon, b_lat, b_lon, max_km: float) -> bool:
    if None in (a_lat, a_lon, b_lat, b_lon):
        return False
    import math
    r = 6371.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lambda = math.radians(b_lon - a_lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h)) <= max_km
