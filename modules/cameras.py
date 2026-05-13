"""Public cameras module — geocodes a place and lists nearby cameras."""

from __future__ import annotations

from typing import Any

from providers.cameras import (
    OSMWebcamsProvider,
    OfficialCamerasProvider,
    WindyWebcamsProvider,
    YouTubeLiveCamerasProvider,
)
from utils.geocode import GeocodeError, geocode


def near_place(
    place: str,
    *,
    radius_km: float = 50.0,
    include_all: bool = False,
    discover: bool = False,
) -> dict[str, Any]:
    official = OfficialCamerasProvider()
    try:
        geo = geocode(place)
        geocoder = geo["source"]
    except GeocodeError as exc:
        # Local fallback: use the nearest curated camera anchor by text
        # matching when a user has a local registry file.
        geo = official.anchor_for_query(place)
        if geo is None:
            raise ValueError(str(exc)) from exc
        geocoder = geo["source"]
    cams = _collect_cameras(
        geo["lat"],
        geo["lon"],
        query=place,
        radius_km=radius_km,
        include_all=include_all,
        discover=discover,
        official_provider=official,
    )
    return {
        "place": geo["name"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "radius_km": radius_km,
        "all": include_all,
        "discover": discover,
        "geocoder": geocoder,
        "cameras": cams,
    }


def near_coords(
    lat: float,
    lon: float,
    *,
    radius_km: float = 50.0,
    include_all: bool = False,
    discover: bool = False,
) -> list[dict[str, Any]]:
    return _collect_cameras(
        lat,
        lon,
        radius_km=radius_km,
        include_all=include_all,
        discover=discover,
    )


def _collect_cameras(
    lat: float,
    lon: float,
    *,
    query: str | None = None,
    radius_km: float,
    include_all: bool,
    discover: bool,
    official_provider: OfficialCamerasProvider | None = None,
) -> list[dict[str, Any]]:
    official = official_provider or OfficialCamerasProvider()
    out = official.near(lat, lon, radius_km=radius_km, include_all=include_all)
    if discover:
        discovered: list[dict[str, Any]] = []
        try:
            discovered.extend(OSMWebcamsProvider().near(lat, lon, radius_km=radius_km))
        except Exception:  # noqa: BLE001
            pass
        try:
            windy = WindyWebcamsProvider()
            if windy.is_available():
                discovered.extend(windy.near(lat, lon, radius_km=radius_km))
        except Exception:  # noqa: BLE001
            pass
        if query:
            try:
                youtube = YouTubeLiveCamerasProvider()
                if youtube.is_available():
                    discovered.extend(
                        youtube.search(
                            query,
                            limit=10,
                            anchor_lat=lat,
                            anchor_lon=lon,
                        )
                    )
            except Exception:  # noqa: BLE001
                pass
        out = _merge_unique(out, discovered)
    out.sort(key=lambda r: r.get("distance_km", 999999.0))
    return out


def _merge_unique(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in [*a, *b]:
        key = _cam_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _cam_key(cam: dict[str, Any]) -> str:
    name = (cam.get("name") or "").strip().lower()
    url = (cam.get("url") or "").strip().lower()
    lat = round(float(cam.get("lat") or 0.0), 4)
    lon = round(float(cam.get("lon") or 0.0), 4)
    return f"{name}|{url}|{lat}|{lon}"
