"""Public camera providers and optional local camera registry.

The repository intentionally ships without hard-coded camera URLs. Everyone
who downloads CelebiPlug gets the same generic discovery logic; local curated
feeds can live in ``camera_registry.local.json`` or the path pointed to by
``CELEBI_CAMERA_REGISTRY``.

CelebiPlug does not surface MOBESE / KGYS / private surveillance cameras under
any condition. Every source must still be whitelisted in :mod:`legal_guard`.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from typing import Any

from legal_guard import LegalGuardError, ensure_source, filter_records
from utils.http import HttpError, get_bytes, get_json

from .base import BaseProvider


_LOCAL_REGISTRY_ENV = "CELEBI_CAMERA_REGISTRY"
_LOCAL_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "camera_registry.local.json"
_BUILTIN_REGISTRY: list[dict[str, Any]] = []


def _haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lambda = math.radians(b_lon - a_lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class OfficialCamerasProvider(BaseProvider):
    """Returns optional curated public cameras near a coordinate.

    Every entry is re-validated through legal_guard before being emitted.
    """

    category = "cameras"
    source_id = "tourism-cam"  # default; entries can override

    def __init__(self, registry: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._registry = registry

    def near(
        self,
        lat: float,
        lon: float,
        *,
        radius_km: float = 50.0,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for cam in self._registry_rows():
            dist = _haversine_km(lat, lon, cam["lat"], cam["lon"])
            if not include_all and dist > radius_km:
                continue
            row = _with_view_metadata(cam)
            row["distance_km"] = round(dist, 2)
            row["fetched_at"] = _now_iso()
            out.append(row)
        out.sort(key=lambda r: r["distance_km"])
        return filter_records("cameras", out)

    def anchor_for_query(self, place: str) -> dict[str, Any] | None:
        """Best-effort local anchor when network geocoding is unavailable."""
        q_norm = _norm_text(place)
        if not q_norm:
            return None
        q_words = set(q_norm.split())
        best: dict[str, Any] | None = None
        best_score = 0
        for cam in self._registry_rows():
            hay = _norm_text(
                f"{cam.get('name', '')} {cam.get('operator', '')} {cam.get('url', '')}"
            )
            if not hay:
                continue
            score = sum(1 for w in q_words if w in hay)
            if q_norm in hay:
                score += 2
            if score > best_score:
                best_score = score
                best = cam
        if not best or best_score <= 0:
            return None
        return {
            "name": best.get("name") or place,
            "lat": best.get("lat"),
            "lon": best.get("lon"),
            "source": "local-camera-registry",
        }

    def snapshot(self, url: str) -> bytes | None:
        """Best-effort snapshot fetch. Returns ``None`` on failure.

        Only follows http(s) URLs. Caller decides whether to surface bytes
        or just metadata.
        """
        if not url or not url.lower().startswith(("http://", "https://")):
            return None
        try:
            return get_bytes(url, timeout=10.0)
        except HttpError:
            return None

    def _registry_rows(self) -> list[dict[str, Any]]:
        if self._registry is not None:
            return _normalize_registry_rows(self._registry)
        return _load_registry()


class OSMWebcamsProvider(BaseProvider):
    """Discovers public webcam records from OSM via Overpass."""

    category = "cameras"
    source_id = "osm-webcam"
    API_URL = "https://overpass-api.de/api/interpreter"

    def near(
        self,
        lat: float,
        lon: float,
        *,
        radius_km: float = 50.0,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        radius_m = int(max(500, min(radius_km * 1000, 120_000)))
        lim = int(max(1, min(limit, 300)))
        query = _build_overpass_query(lat, lon, radius_m, lim)
        data = get_json(self.API_URL, params={"data": query}, timeout=14.0)
        elements = data.get("elements") or []
        out: list[dict[str, Any]] = []
        for el in elements:
            rec = _parse_osm_camera(el, anchor_lat=lat, anchor_lon=lon)
            if rec is not None:
                out.append(rec)
        out = filter_records("cameras", out)
        out.sort(key=lambda r: r.get("distance_km", 999999.0))
        return out[:lim]


class WindyWebcamsProvider(BaseProvider):
    """Discovers public webcams through Windy Webcams API v3."""

    category = "cameras"
    source_id = "windy-webcams"
    API_URL = "https://api.windy.com/webcams/api/v3/webcams"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = (api_key or os.environ.get("WINDY_WEBCAMS_API_KEY") or "").strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def near(
        self,
        lat: float,
        lon: float,
        *,
        radius_km: float = 50.0,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            return []
        radius = max(1, min(int(radius_km), 250))
        lim = max(1, min(int(limit), 50))
        data = get_json(
            self.API_URL,
            params={
                "nearby": f"{lat},{lon},{radius}",
                "limit": lim,
                "offset": 0,
                "lang": "en",
                "include": "categories,images,location,player,urls,user",
            },
            headers={"x-windy-api-key": self.api_key},
            timeout=14.0,
        )
        rows: list[dict[str, Any]] = []
        for item in (data.get("webcams") or []):
            rec = _parse_windy_camera(item, anchor_lat=lat, anchor_lon=lon)
            if rec is not None:
                rows.append(rec)
        rows = filter_records("cameras", rows)
        rows.sort(key=lambda r: r.get("distance_km", 999999.0))
        return rows[:lim]


class YouTubeLiveCamerasProvider(BaseProvider):
    """Discovers public live webcams from YouTube using yt-dlp."""

    category = "cameras"
    source_id = "youtube-live"

    def __init__(self, *, binary: str = "yt-dlp") -> None:
        super().__init__()
        self.binary = binary
        self.binary_path = shutil.which(binary)

    def is_available(self) -> bool:
        return bool(self.binary_path)

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        anchor_lat: float | None = None,
        anchor_lon: float | None = None,
    ) -> list[dict[str, Any]]:
        if not self.binary_path:
            return []
        lim = max(1, min(int(limit), 20))
        rows = _yt_dlp_search_live(
            self.binary_path,
            f"{query} live webcam",
            limit=lim,
            anchor_lat=anchor_lat,
            anchor_lon=anchor_lon,
        )
        rows = filter_records("cameras", rows)
        rows.sort(key=lambda r: r.get("distance_km", 999999.0))
        return rows[:lim]


def _load_registry() -> list[dict[str, Any]]:
    rows = list(_BUILTIN_REGISTRY)
    rows.extend(_load_local_registry())
    return _normalize_registry_rows(rows)


def _load_local_registry() -> list[dict[str, Any]]:
    path = _local_registry_path()
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("cameras")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _local_registry_path() -> Path | None:
    raw = (os.environ.get(_LOCAL_REGISTRY_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _LOCAL_REGISTRY_PATH


def _normalize_registry_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        cam = _normalize_registry_camera(row)
        if cam is not None:
            out.append(cam)
    return out


def _normalize_registry_camera(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        lat = float(row.get("lat"))
        lon = float(row.get("lon"))
    except (TypeError, ValueError):
        return None
    name = str(row.get("name") or "").strip()
    url = str(row.get("url") or "").strip()
    if not name or not url.lower().startswith(("http://", "https://")):
        return None
    source = str(row.get("source") or "tourism-cam").strip().lower()
    try:
        ensure_source("cameras", source)
    except LegalGuardError:
        return None
    cam: dict[str, Any] = {
        "name": name,
        "lat": lat,
        "lon": lon,
        "url": url,
        "operator": str(row.get("operator") or "Local public camera registry").strip(),
        "source": source,
        "snapshot_url": _optional_http_url(row.get("snapshot_url")),
    }
    for key in ("view_hint", "view_bearing_deg"):
        if row.get(key) is not None:
            cam[key] = row[key]
    return cam


def _optional_http_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text.lower().startswith(("http://", "https://")) else None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


_COMPASS_16 = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)


def _normalize_bearing(value: Any) -> float | None:
    if value is None:
        return None
    try:
        deg = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(deg):
        return None
    return round(deg % 360.0, 1)


def _compass_from_bearing(deg: float) -> str:
    idx = int((deg + 11.25) // 22.5) % 16
    return _COMPASS_16[idx]


def _with_view_metadata(cam: dict[str, Any]) -> dict[str, Any]:
    out = dict(cam)
    bearing = _normalize_bearing(out.get("view_bearing_deg"))
    if bearing is not None:
        out["view_bearing_deg"] = bearing
        out["view_compass"] = _compass_from_bearing(bearing)
    hint = out.get("view_hint")
    if hint is not None:
        out["view_hint"] = str(hint).strip() or None
    return out


def _norm_text(value: str) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(text.split())


_CARDINAL_BEARINGS = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}


def _direction_to_bearing(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None
    if "-" in raw:
        left, right = raw.split("-", 1)
        a = _direction_to_bearing(left)
        b = _direction_to_bearing(right)
        if a is None or b is None:
            return None
        span = (b - a) % 360.0
        return _normalize_bearing(a + (span / 2.0))
    if raw in _CARDINAL_BEARINGS:
        return _CARDINAL_BEARINGS[raw]
    return _normalize_bearing(raw)


def _build_overpass_query(lat: float, lon: float, radius_m: int, limit: int) -> str:
    return (
        "[out:json][timeout:20];"
        "("
        f'node(around:{radius_m},{lat},{lon})["man_made"="surveillance"]["surveillance:type"="camera"][~"^(contact:webcam|website|url)$"~"^https?://",i];'
        f'way(around:{radius_m},{lat},{lon})["man_made"="surveillance"]["surveillance:type"="camera"][~"^(contact:webcam|website|url)$"~"^https?://",i];'
        f'relation(around:{radius_m},{lat},{lon})["man_made"="surveillance"]["surveillance:type"="camera"][~"^(contact:webcam|website|url)$"~"^https?://",i];'
        ");"
        f"out center tags {limit};"
    )


def _pick_camera_url(tags: dict[str, Any]) -> str | None:
    for key in ("contact:webcam", "url", "website", "contact:website"):
        value = (tags.get(key) or "").strip()
        if value.lower().startswith(("http://", "https://")):
            return value
    return None


def _parse_osm_camera(el: dict[str, Any], *, anchor_lat: float, anchor_lon: float) -> dict[str, Any] | None:
    tags = el.get("tags") or {}
    url = _pick_camera_url(tags)
    if not url:
        return None
    access = (tags.get("access") or "").strip().lower()
    if access == "private":
        return None
    lat = el.get("lat")
    lon = el.get("lon")
    if lat is None or lon is None:
        center = el.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None
    distance = round(_haversine_km(anchor_lat, anchor_lon, lat_f, lon_f), 2)
    direction_raw = tags.get("camera:direction") or tags.get("direction")
    bearing = _direction_to_bearing(direction_raw)
    hint = (tags.get("description") or tags.get("surveillance:zone") or "").strip() or None
    rec: dict[str, Any] = {
        "name": (tags.get("name") or f"OSM webcam {el.get('type')}:{el.get('id')}").strip(),
        "lat": lat_f,
        "lon": lon_f,
        "url": url,
        "operator": (tags.get("operator") or "OpenStreetMap contributors").strip(),
        "source": "osm-webcam",
        "snapshot_url": None,
        "distance_km": distance,
        "fetched_at": _now_iso(),
        "view_hint": hint,
    }
    if bearing is not None:
        rec["view_bearing_deg"] = bearing
    return _with_view_metadata(rec)


def _parse_windy_camera(item: dict[str, Any], *, anchor_lat: float, anchor_lon: float) -> dict[str, Any] | None:
    loc = item.get("location") or {}
    try:
        lat = float(loc.get("latitude"))
        lon = float(loc.get("longitude"))
    except (TypeError, ValueError):
        return None
    urls = item.get("urls") or {}
    player = item.get("player") or {}
    images = item.get("images") or {}
    current = images.get("current") or {}
    user = item.get("user") or {}

    url = (
        _first_http_url(urls.get("detail"))
        or _first_http_url(player.get("live"))
        or _first_http_url(player.get("daylight"))
        or _first_http_url(player)
    )
    if not url:
        return None
    snapshot_url = _first_http_url(current) or _first_http_url(images.get("daylight"))
    operator = (
        (user.get("name") or "").strip()
        or (item.get("title") or "").strip()
        or "Windy webcam owner"
    )
    title = (item.get("title") or "").strip() or f"Windy webcam {item.get('webcamId')}"
    categories = item.get("categories") or []
    cat_names = [str(c.get("name")).strip() for c in categories if isinstance(c, dict) and c.get("name")]
    hint = ", ".join(cat_names[:3]) if cat_names else None
    rec: dict[str, Any] = {
        "name": title,
        "lat": lat,
        "lon": lon,
        "url": url,
        "operator": operator,
        "source": "windy-webcams",
        "snapshot_url": snapshot_url,
        "distance_km": round(_haversine_km(anchor_lat, anchor_lon, lat, lon), 2),
        "fetched_at": _now_iso(),
        "view_hint": hint,
        "webcam_id": item.get("webcamId"),
    }
    return _with_view_metadata(rec)


def _first_http_url(value: Any) -> str | None:
    if isinstance(value, str):
        v = value.strip()
        return v if v.lower().startswith(("http://", "https://")) else None
    if isinstance(value, dict):
        for candidate in value.values():
            picked = _first_http_url(candidate)
            if picked:
                return picked
    if isinstance(value, list):
        for candidate in value:
            picked = _first_http_url(candidate)
            if picked:
                return picked
    return None


def _yt_dlp_search_live(
    yt_dlp_bin: str,
    query: str,
    *,
    limit: int,
    anchor_lat: float | None,
    anchor_lon: float | None,
) -> list[dict[str, Any]]:
    search_expr = f"ytsearch{limit}:{query}"
    cmd = [
        yt_dlp_bin,
        "--dump-json",
        "--skip-download",
        "--no-warnings",
        "--ignore-no-formats-error",
        search_expr,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=35,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    out = proc.stdout or ""
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in out.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        rec = _parse_youtube_live_item(item, anchor_lat=anchor_lat, anchor_lon=anchor_lon)
        if rec is None:
            continue
        yt_id = str(item.get("id") or "")
        if yt_id and yt_id in seen_ids:
            continue
        if yt_id:
            seen_ids.add(yt_id)
        rows.append(rec)
    return rows


def _parse_youtube_live_item(
    item: dict[str, Any],
    *,
    anchor_lat: float | None,
    anchor_lon: float | None,
) -> dict[str, Any] | None:
    live = item.get("is_live")
    live_status = (item.get("live_status") or "").strip().lower()
    if live is False and live_status not in {"is_live", "was_live"}:
        return None

    video_id = str(item.get("id") or "").strip()
    webpage = (item.get("webpage_url") or "").strip()
    if not webpage and video_id:
        webpage = f"https://www.youtube.com/watch?v={video_id}"
    if not webpage:
        return None

    lat = anchor_lat
    lon = anchor_lon
    loc = item.get("location")
    if isinstance(loc, dict):
        try:
            lat = float(loc.get("latitude"))
            lon = float(loc.get("longitude"))
        except (TypeError, ValueError):
            pass

    if lat is None or lon is None:
        return None

    thumb = _pick_youtube_thumbnail(item)
    channel = str(item.get("uploader") or item.get("channel") or "YouTube channel").strip()
    title = str(item.get("title") or f"YouTube Live webcam {video_id}").strip()
    hint = "YouTube live stream"
    if live_status:
        hint += f" ({live_status})"

    rec: dict[str, Any] = {
        "name": title,
        "lat": float(lat),
        "lon": float(lon),
        "url": webpage,
        "operator": channel,
        "source": "youtube-live",
        "snapshot_url": thumb,
        "distance_km": 0.0,
        "fetched_at": _now_iso(),
        "view_hint": hint,
        "youtube_id": video_id or None,
    }
    if anchor_lat is not None and anchor_lon is not None:
        rec["distance_km"] = round(_haversine_km(anchor_lat, anchor_lon, rec["lat"], rec["lon"]), 2)
    return _with_view_metadata(rec)


def _pick_youtube_thumbnail(item: dict[str, Any]) -> str | None:
    thumbs = item.get("thumbnails")
    if isinstance(thumbs, list):
        for t in reversed(thumbs):
            if isinstance(t, dict):
                url = _first_http_url(t.get("url"))
                if url:
                    return url
    elif isinstance(thumbs, dict):
        for t in thumbs.values():
            if isinstance(t, dict):
                url = _first_http_url(t.get("url"))
                if url:
                    return url
    return _first_http_url(item.get("thumbnail"))
