"""Minimal CLI — ``celebi <command> [args]``.

This is intentionally tiny: argparse, no subcommand framework. Each
subcommand dispatches into the matching ``modules/<name>.py`` and prints
JSON. The studio UI is unchanged.

Examples::

    python3 cli.py weather "Fethiye"
    python3 cli.py news "Fethiye"
    python3 cli.py aircraft TK1923
    python3 cli.py earthquake --min 3
    python3 cli.py wildfire --place "Antalya"
    python3 cli.py cameras "Fethiye"
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from modules import aircraft as aircraft_mod
from modules import cameras as cameras_mod
from modules import earthquake as earthquake_mod
from modules import live as live_mod
from modules import narration as narration_mod
from modules import news as news_mod
from modules import snap as snap_mod
from modules import weather as weather_mod
from modules import wildfire as wildfire_mod  # also used in cmd_film via nearest_hotspot
from utils import film as film_util
from utils import snapshot as snapshot_util
from utils import staticmap
from utils import tts as tts_util


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def cmd_weather(args: argparse.Namespace) -> int:
    if args.lat is not None and args.lon is not None:
        _print(weather_mod.by_coords(args.lat, args.lon, marine=args.marine))
    elif args.place:
        _print(weather_mod.by_city(args.place, marine=args.marine))
    else:
        print("usage: celebi weather <place> | --lat <> --lon <>", file=sys.stderr)
        return 2
    return 0


def cmd_news(args: argparse.Namespace) -> int:
    _print(news_mod.fetch(args.query, limit=args.limit))
    return 0


def _enrich_aircraft(record: dict[str, Any], *, with_map: bool, with_snapshot: bool, open_link: bool) -> dict[str, Any]:
    lat = record.get("lat")
    lon = record.get("lon")
    if lat is None or lon is None:
        return record
    if with_map or with_snapshot:
        frame = staticmap.static_image(lat, lon, zoom=8, width=720, height=480)
        record["map"] = frame
        record["web_link"] = staticmap.web_link(lat, lon, zoom=8)
        if with_snapshot and frame.get("is_image"):
            path = snapshot_util.download(frame["url"])
            record["snapshot_path"] = str(path) if path else None
        if open_link:
            snapshot_util.open_in_browser(record.get("web_link") or frame.get("url"))
    return record


def cmd_aircraft(args: argparse.Namespace) -> int:
    if args.callsign:
        rec = aircraft_mod.by_callsign(args.callsign)
        if rec:
            _enrich_aircraft(rec, with_map=args.map, with_snapshot=args.snapshot, open_link=args.open)
        _print(rec or {"error": f"no public record for callsign {args.callsign}"})
        return 0 if rec else 1
    if args.place:
        payload = aircraft_mod.near_place(args.place, radius_km=args.radius_km)
        for rec in payload.get("aircraft", []):
            _enrich_aircraft(rec, with_map=args.map, with_snapshot=False, open_link=False)
        _print(payload)
        return 0
    if args.lat is not None and args.lon is not None:
        recs = aircraft_mod.near_coords(args.lat, args.lon, radius_km=args.radius_km)
        for rec in recs:
            _enrich_aircraft(rec, with_map=args.map, with_snapshot=False, open_link=False)
        _print({
            "lat": args.lat,
            "lon": args.lon,
            "radius_km": args.radius_km,
            "aircraft": recs,
        })
        return 0
    print("usage: celebi aircraft <callsign> | --place <> | --lat <> --lon <>", file=sys.stderr)
    return 2


def cmd_earthquake(args: argparse.Namespace) -> int:
    _print({
        "count": None,
        "items": earthquake_mod.recent(limit=args.limit, min_magnitude=args.min),
    })
    return 0


def cmd_wildfire(args: argparse.Namespace) -> int:
    if args.place:
        _print(wildfire_mod.active_near(args.place, limit=args.limit))
    else:
        _print({"fires": wildfire_mod.active(limit=args.limit)})
    return 0


def _enrich_camera(cam: dict[str, Any], *, with_snapshot: bool) -> dict[str, Any]:
    lat = cam.get("lat")
    lon = cam.get("lon")
    if lat is None or lon is None:
        return cam
    bearing = cam.get("view_bearing_deg")
    pitch = 45 if bearing is not None else None
    frame = staticmap.static_image(
        lat,
        lon,
        zoom=14,
        width=720,
        height=480,
        bearing=bearing,
        pitch=pitch,
    )
    cam["preview"] = frame
    if with_snapshot:
        # 1) Prefer a real JPEG endpoint when the registry has one.
        # 2) Otherwise fall back to a Mapbox satellite still of the camera location.
        path = None
        if cam.get("snapshot_url"):
            path = snapshot_util.download(cam["snapshot_url"])
        if path is None and frame.get("is_image"):
            path = snapshot_util.download(frame["url"])
        cam["snapshot_path"] = str(path) if path else None
    return cam


def cmd_cameras(args: argparse.Namespace) -> int:
    try:
        if args.place:
            payload = cameras_mod.near_place(
                args.place,
                radius_km=args.radius_km,
                include_all=args.all,
                discover=args.discover,
            )
            payload["all"] = args.all
            payload["discover"] = args.discover
            cams = payload.get("cameras", [])
        elif args.lat is not None and args.lon is not None:
            cams = cameras_mod.near_coords(
                args.lat,
                args.lon,
                radius_km=args.radius_km,
                include_all=args.all,
                discover=args.discover,
            )
            payload = {
                "lat": args.lat,
                "lon": args.lon,
                "radius_km": args.radius_km,
                "all": args.all,
                "discover": args.discover,
                "cameras": cams,
            }
        else:
            print("usage: celebi cameras <place> | --lat <> --lon <>", file=sys.stderr)
            return 2
    except ValueError as exc:
        _print({"error": str(exc)})
        return 1

    for cam in cams:
        _enrich_camera(cam, with_snapshot=args.snapshot)
    if args.open and cams:
        snapshot_util.open_in_browser(cams[0].get("url") or "")
    _print(payload)
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    try:
        payload = live_mod.snapshot(args.place, marine=args.marine, radius_km=args.radius_km)
    except ValueError as exc:
        _print({"error": str(exc)})
        return 1
    if args.snapshot and payload["map"].get("is_image"):
        path = snapshot_util.download(payload["map"]["url"])
        payload["snapshot_path"] = str(path) if path else None
    if args.open:
        snapshot_util.open_in_browser(payload.get("web_link") or payload["map"]["url"])
    _print(payload)
    return 0


def cmd_snap_aircraft(args: argparse.Namespace) -> int:
    payload = snap_mod.snap_aircraft(args.callsign)
    _print(payload)
    return 0 if payload.get("snapshot_path") or payload.get("card_path") or not payload.get("error") else 1


def cmd_snap_camera(args: argparse.Namespace) -> int:
    if args.place:
        payload = snap_mod.snap_camera(args.place, radius_km=args.radius_km, discover=args.discover)
    elif args.lat is not None and args.lon is not None:
        payload = snap_mod.snap_camera(lat=args.lat, lon=args.lon, radius_km=args.radius_km, discover=args.discover)
    else:
        print("usage: celebi snap-camera <place> | --lat <> --lon <>", file=sys.stderr)
        return 2
    _print(payload)
    return 0 if payload.get("snapshot_path") or not payload.get("error") else 1


def cmd_snap_wildfire(args: argparse.Namespace) -> int:
    payload = snap_mod.snap_wildfire(args.place)
    _print(payload)
    return 0 if not payload.get("error") else 1


def cmd_film(args: argparse.Namespace) -> int:
    import time as _time
    base = args.base_url.rstrip("/")

    place = args.place
    lat: float | None = args.lat
    lon: float | None = args.lon

    # --wildfire: find nearest fire hotspot and fly there
    wildfire_place = getattr(args, "wildfire", None)
    if wildfire_place:
        hotspot = wildfire_mod.nearest_hotspot(wildfire_place)
        if hotspot is None:
            _print({"error": f"no active fires found near {wildfire_place}"})
            return 1
        lat, lon = hotspot["lat"], hotspot["lon"]
        place = place or wildfire_place
        if not args.narrate:
            args.narrate = "auto"

    # --geojson: extract centroid from GeoJSON file
    geojson_path = getattr(args, "geojson", None)
    if geojson_path:
        center = film_util.extract_center_from_geojson(geojson_path)
        if center is None:
            _print({"error": f"could not extract coordinates from {geojson_path}"})
            return 1
        lat, lon = center
        if not args.narrate:
            args.narrate = "auto"

    narrate = None
    if args.narrate:
        narrate = "auto" if args.narrate == "auto" else args.narrate

    url = film_util.build_autopilot_url(
        base,
        place=place,
        lat=lat,
        lon=lon,
        radius=args.radius,
        aspect=args.aspect,
        preset=args.preset,
        poi=args.poi,
        duration=args.duration,
        narrate=narrate,
    )
    started = _time.time()
    launched = film_util.launch_browser(url)
    if not launched:
        _print({"error": "could not launch Chrome — open this URL manually", "url": url})
        return 1
    expected = args.duration or (36 if args.poi == "skip" else 60)
    timeout = max(expected + 45, args.timeout)
    mp4 = film_util.watch_downloads(timeout_seconds=timeout, started_at=started)
    if mp4 is None:
        _print({"error": f"no MP4 appeared in ~/Downloads within {int(timeout)}s", "url": url})
        return 1
    payload = {
        "mp4_path": str(mp4),
        "size_bytes": mp4.stat().st_size,
        "url": url,
        "narrated": bool(narrate),
        "place": place,
        "aspect": args.aspect,
        "preset": args.preset,
    }
    _print(payload)
    return 0


def cmd_narrate(args: argparse.Namespace) -> int:
    text = args.text or (narration_mod.auto_text_for(args.place, lang=args.lang) if args.place else None)
    if not text:
        print("usage: celebi narrate <text> | --place <place>", file=sys.stderr)
        return 2
    if args.text_only:
        _print({"text": text})
        return 0
    result = tts_util.synthesize(text, lang=args.lang)
    if result is None:
        _print({"error": "local TTS unavailable — install `espeak-ng` (Linux) or run on macOS", "text": text})
        return 1
    _print({"text": text, "audio_path": str(result.path), "mime": result.mime})
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    if args.place:
        try:
            from utils.geocode import geocode
            geo = geocode(args.place)
            lat, lon = geo["lat"], geo["lon"]
            name = geo["name"]
        except Exception as exc:  # noqa: BLE001
            _print({"error": str(exc)})
            return 1
    elif args.lat is not None and args.lon is not None:
        lat, lon, name = args.lat, args.lon, None
    else:
        print("usage: celebi map <place> | --lat <> --lon <>", file=sys.stderr)
        return 2
    frame = staticmap.static_image(lat, lon, zoom=args.zoom, width=args.width, height=args.height)
    payload: dict[str, Any] = {
        "place": name,
        "lat": lat,
        "lon": lon,
        "map": frame,
        "web_link": staticmap.web_link(lat, lon, zoom=args.zoom),
    }
    if args.snapshot and frame.get("is_image"):
        path = snapshot_util.download(frame["url"])
        payload["snapshot_path"] = str(path) if path else None
    if args.open:
        snapshot_util.open_in_browser(payload["web_link"])
    _print(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="celebi",
        description="CelebiPlug local geo-intelligence CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_w = sub.add_parser("weather", help="Current weather for a place or coords")
    p_w.add_argument("place", nargs="?")
    p_w.add_argument("--lat", type=float)
    p_w.add_argument("--lon", type=float)
    p_w.add_argument("--marine", action="store_true", help="Include sea suitability")
    p_w.set_defaults(func=cmd_weather)

    p_n = sub.add_parser("news", help="Local news by RSS or NewsAPI")
    p_n.add_argument("query", nargs="?")
    p_n.add_argument("--limit", type=int, default=15)
    p_n.set_defaults(func=cmd_news)

    p_a = sub.add_parser("aircraft", help="Aircraft by callsign or near place/coords")
    p_a.add_argument("callsign", nargs="?")
    p_a.add_argument("--place", help="Search aircraft near this place")
    p_a.add_argument("--lat", type=float)
    p_a.add_argument("--lon", type=float)
    p_a.add_argument("--radius-km", dest="radius_km", type=float, default=50.0)
    p_a.add_argument("--map", action="store_true", help="Include a static map URL with a pin at the aircraft position")
    p_a.add_argument("--snapshot", action="store_true", help="Download a one-frame map snapshot to /tmp and return the path")
    p_a.add_argument("--open", action="store_true", help="Open the map link in the default browser")
    p_a.set_defaults(func=cmd_aircraft)

    p_e = sub.add_parser("earthquake", help="Recent earthquakes (AFAD/Kandilli/USGS)")
    p_e.add_argument("--limit", type=int, default=50)
    p_e.add_argument("--min", type=float, default=0.0, help="Minimum magnitude")
    p_e.set_defaults(func=cmd_earthquake)

    p_f = sub.add_parser("wildfire", help="Active fires (NASA FIRMS)")
    p_f.add_argument("--place", help="Filter to a region around this place")
    p_f.add_argument("--limit", type=int, default=500)
    p_f.set_defaults(func=cmd_wildfire)

    p_c = sub.add_parser("cameras", help="Public/official cameras near a place")
    p_c.add_argument("place", nargs="?")
    p_c.add_argument("--lat", type=float)
    p_c.add_argument("--lon", type=float)
    p_c.add_argument("--radius-km", dest="radius_km", type=float, default=50.0)
    p_c.add_argument("--all", action="store_true", help="Return all curated public cameras, ignore radius filter")
    p_c.add_argument("--discover", action="store_true", help="Discover additional public webcams from OSM/Windy/YouTube")
    p_c.add_argument("--snapshot", action="store_true", help="Save a single-frame still per camera and return the path")
    p_c.add_argument("--open", action="store_true", help="Open the first camera's live URL in the default browser")
    p_c.set_defaults(func=cmd_cameras)

    p_live = sub.add_parser("live", help="Combined live view: weather + cameras + map still + activity counts")
    p_live.add_argument("place")
    p_live.add_argument("--marine", action="store_true", help="Include sea suitability")
    p_live.add_argument("--radius-km", dest="radius_km", type=float, default=50.0)
    p_live.add_argument("--snapshot", action="store_true", help="Download the satellite still to /tmp and return the path")
    p_live.add_argument("--open", action="store_true", help="Open the location's web map in the default browser")
    p_live.set_defaults(func=cmd_live)

    p_sa = sub.add_parser("snap-aircraft", help="Composite PNG: aircraft pin on map + info card")
    p_sa.add_argument("callsign")
    p_sa.set_defaults(func=cmd_snap_aircraft)

    p_sc = sub.add_parser("snap-camera", help="Single-frame PNG from a public camera (or satellite fallback)")
    p_sc.add_argument("place", nargs="?")
    p_sc.add_argument("--lat", type=float)
    p_sc.add_argument("--lon", type=float)
    p_sc.add_argument("--radius-km", dest="radius_km", type=float, default=100.0)
    p_sc.add_argument("--discover", action="store_true", help="Include discovered public webcams when picking a frame")
    p_sc.set_defaults(func=cmd_snap_camera)

    p_sf = sub.add_parser("snap-wildfire", help="Composite PNG: nearest active fire hotspot pin on map + NASA FIRMS card")
    p_sf.add_argument("place", help="Region to search for fires (e.g. 'Antalya')")
    p_sf.set_defaults(func=cmd_snap_wildfire)

    p_film = sub.add_parser("film", help="Drive the studio autopilot and return the recorded MP4 path")
    p_film.add_argument("place", nargs="?")
    p_film.add_argument("--lat", type=float)
    p_film.add_argument("--lon", type=float)
    p_film.add_argument("--radius", type=int, help="meters")
    p_film.add_argument("--aspect", default="16-9", choices=["16-9", "9-16", "1-1", "4-5", "21-9", "4-3", "3-4"])
    p_film.add_argument("--preset", default="showcase", choices=["showcase", "orbit", "reveal", "flyover", "top-down"])
    p_film.add_argument("--poi", default="skip", help="skip | auto | auto:N | names:A,B")
    p_film.add_argument("--duration", type=int, help="seconds — override default 36/60")
    p_film.add_argument("--narrate", help="auto | <text> — TTS narration baked into MP4")
    p_film.add_argument("--wildfire", metavar="PLACE", help="Find nearest NASA FIRMS fire near PLACE and fly there with narration")
    p_film.add_argument("--geojson", metavar="FILE", help="GeoJSON file — extract centroid and film that location")
    p_film.add_argument("--base-url", default="http://127.0.0.1:5001")
    p_film.add_argument("--timeout", type=float, default=180.0)
    p_film.set_defaults(func=cmd_film)

    p_n = sub.add_parser("narrate", help="Build narration text (and audio bytes if TTS engine available)")
    p_n.add_argument("text", nargs="?")
    p_n.add_argument("--place", help="auto-generate from live bundle for this place")
    p_n.add_argument("--lang", default="tr", choices=["tr", "de", "en"])
    p_n.add_argument("--text-only", action="store_true", help="emit only the script, skip TTS")
    p_n.set_defaults(func=cmd_narrate)

    p_m = sub.add_parser("map", help="Static satellite map URL (and optional one-frame snapshot)")
    p_m.add_argument("place", nargs="?")
    p_m.add_argument("--lat", type=float)
    p_m.add_argument("--lon", type=float)
    p_m.add_argument("--zoom", type=int, default=13)
    p_m.add_argument("--width", type=int, default=720)
    p_m.add_argument("--height", type=int, default=480)
    p_m.add_argument("--snapshot", action="store_true", help="Save the rendered PNG to /tmp and return the path")
    p_m.add_argument("--open", action="store_true", help="Open the location in the default browser")
    p_m.set_defaults(func=cmd_map)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
