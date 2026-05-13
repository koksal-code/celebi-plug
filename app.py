import os
from ipaddress import ip_address, ip_network
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request

import legal_guard
from modules import aircraft as aircraft_mod
from modules import cameras as cameras_mod
from modules import earthquake as earthquake_mod
from modules import live as live_mod
from modules import narration as narration_mod
from modules import news as news_mod
from modules import snap as snap_mod
from modules import weather as weather_mod
from modules import wildfire as wildfire_mod
from utils import staticmap
from utils import tts as tts_util
from utils.geocode import GeocodeError, geocode
from utils.http import HttpError, get_bytes

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

LOCAL_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("::1/128"),
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_local_request() -> bool:
    """Allow only loopback browser requests."""
    raw_host = (request.host or "").lower()
    if raw_host.startswith("["):
        host = raw_host.partition("]")[0].strip("[]")
    else:
        host = raw_host.split(":", 1)[0]
    if host not in LOCAL_HOSTS:
        return False
    try:
        remote = ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return any(remote in network for network in LOCAL_NETWORKS)


def load_env_token() -> str:
    """Resolve MAPBOX_TOKEN from env var or local .env (pk.* only)."""
    env_var = (os.environ.get("MAPBOX_TOKEN") or "").strip().strip('"').strip("'")
    if env_var.startswith("pk."):
        return env_var

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return ""

    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() != "MAPBOX_TOKEN":
                continue
            value = value.strip().strip('"').strip("'")
            return value if value.startswith("pk.") else ""
    except OSError:
        return ""
    return ""


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.before_request
def guard_local_only():
    if not is_local_request():
        abort(403)


@app.route("/")
def index():
    return render_template("index.html", env_token=load_env_token())


@app.route("/record")
def record_disabled():
    return (
        "server-side /record is disabled.\n"
        "Use a same-machine GUI browser at http://127.0.0.1:5001; agents can record through the studio autopilot/API.\n",
        410,
    )


# ---------------------------------------------------------------------------
# Geo-intelligence API. All endpoints are read-only and local-only (guarded
# above by ``guard_local_only``). Errors come back as ``{ "error": ... }``
# with the matching HTTP status — no stack traces leak to the client.
# ---------------------------------------------------------------------------


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "celebi-plug",
        "modules": {
            "weather": legal_guard.list_sources("weather"),
            "news": legal_guard.list_sources("news"),
            "aircraft": legal_guard.list_sources("aircraft"),
            "earthquake": legal_guard.list_sources("earthquake"),
            "wildfire": legal_guard.list_sources("wildfire"),
            "cameras": legal_guard.list_sources("cameras"),
        },
        "studio": "/",
    })


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _coords_or_place():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    place = (request.args.get("q") or request.args.get("place") or "").strip()
    if lat is not None and lon is not None:
        return ("coords", lat, lon, None)
    if place:
        return ("place", None, None, place)
    return (None, None, None, None)


@app.route("/api/weather")
def api_weather():
    mode, lat, lon, place = _coords_or_place()
    marine = request.args.get("marine") in {"1", "true", "yes"}
    try:
        if mode == "coords":
            payload = weather_mod.by_coords(lat, lon, marine=marine)
        elif mode == "place":
            payload = weather_mod.by_city(place, marine=marine)
        else:
            return _err("provide ?lat=&lon= or ?q=<place>")
    except ValueError as exc:
        return _err(str(exc), 404)
    return jsonify(payload)


@app.route("/api/news")
def api_news():
    query = (request.args.get("q") or request.args.get("place") or "").strip() or None
    limit = request.args.get("limit", type=int) or 15
    return jsonify({"query": query, "items": news_mod.fetch(query, limit=limit)})


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def _attach_aircraft_map(record: dict) -> dict:
    lat, lon = record.get("lat"), record.get("lon")
    if lat is None or lon is None:
        return record
    record["map"] = staticmap.static_image(lat, lon, zoom=8, width=720, height=480)
    record["web_link"] = staticmap.web_link(lat, lon, zoom=8)
    return record


@app.route("/api/aircraft")
def api_aircraft():
    with_map = _truthy(request.args.get("map"))
    callsign = (request.args.get("callsign") or "").strip()
    if callsign:
        record = aircraft_mod.by_callsign(callsign)
        if not record:
            return _err(f"no public record for callsign {callsign}", 404)
        if with_map:
            _attach_aircraft_map(record)
        return jsonify(record)
    radius_km = request.args.get("radius_km", type=float) or 50.0
    mode, lat, lon, place = _coords_or_place()
    try:
        if mode == "coords":
            recs = aircraft_mod.near_coords(lat, lon, radius_km=radius_km)
            if with_map:
                for r in recs:
                    _attach_aircraft_map(r)
            return jsonify({"lat": lat, "lon": lon, "radius_km": radius_km, "aircraft": recs})
        if mode == "place":
            payload = aircraft_mod.near_place(place, radius_km=radius_km)
            if with_map:
                for r in payload.get("aircraft", []):
                    _attach_aircraft_map(r)
            return jsonify(payload)
    except ValueError as exc:
        return _err(str(exc), 404)
    return _err("provide ?callsign=, or ?lat=&lon=, or ?q=<place>")


@app.route("/api/earthquakes")
def api_earthquakes():
    limit = request.args.get("limit", type=int) or 50
    min_mag = request.args.get("min", type=float) or 0.0
    try:
        items = earthquake_mod.recent(limit=limit, min_magnitude=min_mag)
    except Exception as exc:  # noqa: BLE001 — surface upstream errors uniformly
        return _err(f"upstream error: {exc}", 502)
    return jsonify({"count": len(items), "items": items})


@app.route("/api/wildfires")
def api_wildfires():
    limit = request.args.get("limit", type=int) or 500
    bbox_raw = (request.args.get("bbox") or "").strip()
    bbox = None
    if bbox_raw:
        try:
            west, south, east, north = (float(p) for p in bbox_raw.split(","))
            bbox = (west, south, east, north)
        except ValueError:
            return _err("bbox must be west,south,east,north", 400)
    mode, lat, lon, place = _coords_or_place()
    try:
        if mode == "place":
            return jsonify(wildfire_mod.active_near(place, limit=limit))
        return jsonify({
            "bbox": list(bbox) if bbox else None,
            "fires": wildfire_mod.active(bbox=bbox, limit=limit),
        })
    except ValueError as exc:
        return _err(str(exc), 404)


def _attach_camera_preview(cam: dict) -> dict:
    lat, lon = cam.get("lat"), cam.get("lon")
    if lat is None or lon is None:
        return cam
    cam["preview"] = staticmap.static_image(lat, lon, zoom=14, width=720, height=480)
    return cam


@app.route("/api/cameras")
def api_cameras():
    radius_km = request.args.get("radius_km", type=float) or 50.0
    with_preview = _truthy(request.args.get("map")) or _truthy(request.args.get("preview"))
    mode, lat, lon, place = _coords_or_place()
    try:
        if mode == "coords":
            cams = cameras_mod.near_coords(lat, lon, radius_km=radius_km)
        elif mode == "place":
            payload = cameras_mod.near_place(place, radius_km=radius_km)
            cams = payload["cameras"]
        else:
            return _err("provide ?lat=&lon= or ?q=<place>")
    except ValueError as exc:
        return _err(str(exc), 404)
    if with_preview:
        for cam in cams:
            _attach_camera_preview(cam)
    if mode == "place":
        return jsonify(payload)
    return jsonify({"lat": lat, "lon": lon, "radius_km": radius_km, "cameras": cams})


@app.route("/api/live")
def api_live():
    mode, lat, lon, place = _coords_or_place()
    radius_km = request.args.get("radius_km", type=float) or 50.0
    marine = _truthy(request.args.get("marine"))
    if mode != "place":
        return _err("provide ?q=<place>")
    try:
        return jsonify(live_mod.snapshot(place, marine=marine, radius_km=radius_km))
    except ValueError as exc:
        return _err(str(exc), 404)


@app.route("/api/map")
def api_map():
    mode, lat, lon, place = _coords_or_place()
    zoom = request.args.get("zoom", type=int) or 13
    width = request.args.get("width", type=int) or 720
    height = request.args.get("height", type=int) or 480
    name = None
    try:
        if mode == "place":
            geo = geocode(place)
            lat, lon, name = geo["lat"], geo["lon"], geo["name"]
        elif mode != "coords":
            return _err("provide ?lat=&lon= or ?q=<place>")
    except GeocodeError as exc:
        return _err(str(exc), 404)
    frame = staticmap.static_image(lat, lon, zoom=zoom, width=width, height=height)
    return jsonify({
        "place": name,
        "lat": lat,
        "lon": lon,
        "map": frame,
        "web_link": staticmap.web_link(lat, lon, zoom=zoom),
    })


@app.route("/api/snapshot.png")
def api_snapshot_png():
    """Proxy a static-map URL as a binary image response.

    Only Mapbox Static Images (api.mapbox.com) URLs are allowed — we are
    not a generic HTTP proxy. The browser fetches a one-frame PNG.
    """
    url = request.args.get("url", "")
    if not url.startswith("https://api.mapbox.com/"):
        # Build one from coords if the agent did not pre-compute it.
        mode, lat, lon, place = _coords_or_place()
        zoom = request.args.get("zoom", type=int) or 13
        if mode == "place":
            try:
                geo = geocode(place)
                lat, lon = geo["lat"], geo["lon"]
            except GeocodeError as exc:
                return _err(str(exc), 404)
        if lat is None or lon is None:
            return _err("provide ?url=<mapbox-static-url> or ?q=<place> or ?lat=&lon=")
        frame = staticmap.static_image(lat, lon, zoom=zoom)
        if not frame.get("is_image"):
            return _err("MAPBOX_TOKEN missing — cannot render a still frame", 503)
        url = frame["url"]
    try:
        body = get_bytes(url, timeout=15.0)
    except HttpError as exc:
        return _err(f"upstream {exc.status}: {exc}", 502)
    return Response(body, mimetype="image/png")


@app.route("/api/snap/aircraft")
def api_snap_aircraft():
    callsign = (request.args.get("callsign") or "").strip()
    if not callsign:
        return _err("provide ?callsign=")
    payload = snap_mod.snap_aircraft(callsign)
    status = 200 if not payload.get("error") else 404
    return jsonify(payload), status


@app.route("/api/snap/camera")
def api_snap_camera():
    radius_km = request.args.get("radius_km", type=float) or 100.0
    mode, lat, lon, place = _coords_or_place()
    if mode == "place":
        payload = snap_mod.snap_camera(place, radius_km=radius_km)
    elif mode == "coords":
        payload = snap_mod.snap_camera(lat=lat, lon=lon, radius_km=radius_km)
    else:
        return _err("provide ?lat=&lon= or ?q=<place>")
    status = 200 if not payload.get("error") else 404
    return jsonify(payload), status


@app.route("/api/narration")
def api_narration():
    """Return narration audio bytes for in-browser playback.

    Query: ``?text=<...>`` to TTS a literal string, ``?q=<place>&auto=1``
    to auto-build narration from the live bundle, ``?text=&dry=1`` to just
    return the generated text without invoking the local TTS engine.
    """
    explicit_text = request.args.get("text", "").strip()
    place = (request.args.get("q") or "").strip()
    lang = (request.args.get("lang") or "tr").strip()
    auto = _truthy(request.args.get("auto"))
    dry = _truthy(request.args.get("dry"))

    if explicit_text:
        text = explicit_text
    elif (auto or place) and place:
        text = narration_mod.auto_text_for(place, lang=lang)
    else:
        return _err("provide ?text=<...> or ?q=<place>&auto=1")

    if dry:
        return jsonify({"text": text, "lang": lang})

    if not tts_util.is_available():
        return jsonify({"text": text, "lang": lang, "audio_available": False}), 503

    result = tts_util.synthesize(text, lang=lang)
    if result is None or not result.path.exists():
        return jsonify({"text": text, "lang": lang, "audio_available": False}), 502

    try:
        body = result.path.read_bytes()
    finally:
        try:
            result.path.unlink()
        except OSError:
            pass
    response = Response(body, mimetype=result.mime)
    response.headers["X-Celebi-Narration-Text"] = text.encode("ascii", "replace").decode("ascii")
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", host="127.0.0.1", port=port)
