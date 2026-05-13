"""Snap module — single-frame artifact delivery.

``snap_aircraft(callsign)``    → composite PNG with map + pin + info card
``snap_camera(place)``         → real JPEG when registry has snapshot_url,
                                 otherwise satellite still of the location

When Pillow is installed, info cards are baked onto the PNG. When it is
not, callers receive the raw map PNG + a JSON sidecar with the metadata
so the chat client can lay them out side-by-side.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any

from utils import composite, snapshot, staticmap

from . import aircraft as aircraft_mod
from . import cameras as cameras_mod
from . import wildfire as wildfire_mod


def _fmt(value: Any, unit: str = "", digits: int = 0) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if digits:
            return f"{value:.{digits}f}{unit}"
        return f"{round(value)}{unit}"
    return f"{value}{unit}"


def _heading_label(deg: float | None) -> str:
    if deg is None:
        return "—"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg % 360) / 45 + 0.5) % 8
    return f"{round(deg)}° {dirs[idx]}"


def snap_aircraft(callsign: str, *, output: Path | None = None) -> dict[str, Any]:
    rec = aircraft_mod.by_callsign(callsign)
    if not rec:
        return {"error": f"no public record for callsign {callsign}", "callsign": callsign}
    lat = rec.get("lat")
    lon = rec.get("lon")
    if lat is None or lon is None:
        return {"error": "aircraft position unavailable", "callsign": callsign, "record": rec}

    frame = staticmap.static_image(lat, lon, zoom=8, width=900, height=600)
    web_link = staticmap.web_link(lat, lon, zoom=8)

    payload: dict[str, Any] = {
        "callsign": rec.get("callsign") or callsign,
        "origin_country": rec.get("origin_country"),
        "lat": lat,
        "lon": lon,
        "altitude_m": rec.get("baro_altitude_m"),
        "speed_kmh": rec.get("speed_kmh"),
        "heading": rec.get("heading"),
        "vertical_rate_ms": rec.get("vertical_rate_ms"),
        "on_ground": rec.get("on_ground"),
        "source": "opensky" if "origin_country" in rec else "adsb-lol",
        "map": frame,
        "web_link": web_link,
        "snapshot_path": None,
        "card_path": None,
    }

    if not frame.get("is_image"):
        return payload  # no Mapbox token → just JSON + OSM link

    bg = snapshot.download(frame["url"])
    if bg is None:
        return payload
    payload["snapshot_path"] = str(bg)

    if composite.is_available():
        alt_label = _fmt(rec.get("baro_altitude_m"), " m")
        spd_label = _fmt(rec.get("speed_kmh"), " km/h")
        vs = rec.get("vertical_rate_ms")
        vs_label = "level"
        if isinstance(vs, (int, float)):
            if vs > 0.5:
                vs_label = f"climbing {round(vs * 60)} m/min"
            elif vs < -0.5:
                vs_label = f"descending {round(-vs * 60)} m/min"
        lines = [
            f"Origin   {payload['origin_country'] or '—'}",
            f"Altitude {alt_label}",
            f"Speed    {spd_label}",
            f"Heading  {_heading_label(rec.get('heading'))}",
            f"Vertical {vs_label}",
            f"Source   {payload['source']}",
        ]
        out = output or Path(tempfile.mkstemp(prefix="celebi-aircraft-", suffix=".png")[1])
        card = composite.compose_card(
            bg,
            title=payload["callsign"] or callsign,
            subtitle=f"CelebiPlug · live · {payload['source']}",
            lines=lines,
            output=out,
        )
        if card is not None:
            payload["card_path"] = str(card)
            # write a small JSON sidecar so the chat client can show both
            sidecar = card.with_suffix(".json")
            sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            payload["json_path"] = str(sidecar)
    return payload


def snap_wildfire(place: str, *, output: Path | None = None) -> dict[str, Any]:
    """Composite PNG: nearest active fire hotspot pin on map + NASA FIRMS info card."""
    hotspot = wildfire_mod.nearest_hotspot(place)
    if not hotspot:
        return {"error": f"no active fires within 500 km of {place}", "place": place}

    lat, lon = hotspot["lat"], hotspot["lon"]
    frame = staticmap.static_image(lat, lon, zoom=11, width=900, height=600)
    web_link = staticmap.web_link(lat, lon, zoom=11)

    payload: dict[str, Any] = {
        "place": hotspot["place"],
        "hotspot": hotspot,
        "map": frame,
        "web_link": web_link,
        "snapshot_path": None,
        "card_path": None,
    }

    if not frame.get("is_image"):
        return payload

    bg = snapshot.download(frame["url"])
    if bg is None:
        return payload
    payload["snapshot_path"] = str(bg)

    if composite.is_available():
        frp = hotspot.get("frp")
        conf = hotspot.get("confidence")
        total = hotspot.get("total_fires")
        dist = hotspot.get("distance_from_center_km")
        place_short = hotspot["place"].split(",")[0]
        lines = [
            f"Lat/Lon     {lat:.4f}, {lon:.4f}",
            f"FRP         {_fmt(frp, ' MW')}  (fire radiative power)",
            f"Confidence  {conf if conf is not None else '—'}%",
            f"Active fires {total} hotspots in area",
            f"Dist from {place_short}  {dist} km",
            f"Acquired    {hotspot.get('acquired_at') or '—'}",
            f"Satellite   {hotspot.get('satellite') or 'MODIS/VIIRS'}",
        ]
        out = output or Path(tempfile.mkstemp(prefix="celebi-fire-", suffix=".png")[1])
        card = composite.compose_card(
            bg,
            title=f"ACTIVE FIRE · {place_short.upper()}",
            subtitle="CelebiPlug · NASA FIRMS · public-domain",
            lines=lines,
            output=out,
        )
        if card is not None:
            payload["card_path"] = str(card)
            sidecar = card.with_suffix(".json")
            sidecar.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            payload["json_path"] = str(sidecar)
    return payload


def snap_camera(
    place: str | None = None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 100.0,
    discover: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    if place:
        bundle = cameras_mod.near_place(place, radius_km=radius_km, discover=discover)
        cams = bundle["cameras"]
        anchor = (bundle["lat"], bundle["lon"])
    elif lat is not None and lon is not None:
        cams = cameras_mod.near_coords(lat, lon, radius_km=radius_km, discover=discover)
        anchor = (lat, lon)
    else:
        return {"error": "provide place or lat/lon"}

    # Auto-discover when registry has no results within radius
    if not cams and not discover:
        try:
            if place:
                auto_bundle = cameras_mod.near_place(
                    place, radius_km=radius_km * 3, discover=True
                )
                cams = auto_bundle["cameras"]
            else:
                cams = cameras_mod.near_coords(
                    anchor[0], anchor[1], radius_km=radius_km * 3, discover=True
                )
        except Exception:  # noqa: BLE001
            pass

    if not cams:
        return {"error": f"no public camera found within {radius_km} km", "anchor": anchor}

    cam = cams[0]
    cam_lat, cam_lon = cam["lat"], cam["lon"]

    # 1) Prefer a real JPEG snapshot URL when the registry has one.
    real_frame_path: Path | None = None
    if cam.get("snapshot_url"):
        real_frame_path = snapshot.download(cam["snapshot_url"])
    payload: dict[str, Any] = dict(cam)
    payload["frame_source"] = "live-snapshot" if real_frame_path else "satellite-fallback"
    payload["snapshot_path"] = str(real_frame_path) if real_frame_path else None

    # 2) Always include a Mapbox satellite still of the camera location.
    frame = staticmap.static_image(cam_lat, cam_lon, zoom=14, width=900, height=600)
    payload["preview"] = frame
    payload["web_link"] = staticmap.web_link(cam_lat, cam_lon, zoom=14)
    if real_frame_path is None and frame.get("is_image"):
        bg = snapshot.download(frame["url"])
        if bg is not None:
            payload["snapshot_path"] = str(bg)
            if composite.is_available():
                lines = [
                    f"Operator {payload['operator']}",
                    f"Distance {payload.get('distance_km', 0):.1f} km",
                    f"Source   {payload['source']}",
                    "Frame    satellite-fallback (no live JPEG)",
                ]
                out = output or Path(tempfile.mkstemp(prefix="celebi-cam-", suffix=".png")[1])
                card = composite.compose_card(
                    bg,
                    title=payload["name"],
                    subtitle="CelebiPlug · public camera",
                    lines=lines,
                    output=out,
                )
                if card is not None:
                    payload["card_path"] = str(card)
    return payload
