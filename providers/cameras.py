"""Official cameras registry.

This is intentionally a *curated whitelist*. CelebiPlug does not scrape
MOBESE / KGYS / private surveillance cameras under any condition.

Each entry is an explicit assertion that the camera is operated by a
public body (tourism office, national park, road authority) for public
viewing. To add a camera, append a row here AND make sure its
``source_id`` is whitelisted in :mod:`legal_guard`.
"""

from __future__ import annotations

import math
from typing import Any

from legal_guard import filter_records
from utils.http import HttpError, get_bytes

from .base import BaseProvider


# (lat, lon, name, url, source_id, operator, snapshot_url?)
_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "Karayolları Bolu Dağı Tüneli",
        "lat": 40.7237,
        "lon": 31.3942,
        "url": "https://www.kgm.gov.tr/Sayfalar/KGM/SiteTr/Trafik/Kameralar/Kameralar.aspx",
        "operator": "T.C. Karayolları Genel Müdürlüğü",
        "source": "kgm-official",
        "snapshot_url": None,
    },
    {
        "name": "Ölüdeniz Belcekız Plajı Canlı",
        "lat": 36.5500,
        "lon": 29.1167,
        "url": "https://www.fethiye.bel.tr/canli-yayin",
        "operator": "Fethiye Belediyesi",
        "source": "tourism-cam",
        "snapshot_url": None,
    },
    {
        "name": "Kapadokya Balon Vadisi",
        "lat": 38.6431,
        "lon": 34.8289,
        "url": "https://www.cappadociaballoons.com/livecam",
        "operator": "Göreme Tarihi Millî Parkı (public viewer)",
        "source": "tourism-cam",
        "snapshot_url": None,
    },
    {
        "name": "Boğaziçi Köprüsü Asya yakası",
        "lat": 41.0419,
        "lon": 29.0334,
        "url": "https://www.ibb.istanbul/CanliYayin",
        "operator": "İstanbul Büyükşehir Belediyesi - canlı yayın",
        "source": "tourism-cam",
        "snapshot_url": None,
    },
    {
        "name": "Uludağ Milli Parkı",
        "lat": 40.0860,
        "lon": 29.1382,
        "url": "https://uludagcanli.com",
        "operator": "Uludağ Milli Parkı (public viewer)",
        "source": "national-park",
        "snapshot_url": None,
    },
]


def _haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lambda = math.radians(b_lon - a_lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class OfficialCamerasProvider(BaseProvider):
    """Returns curated public cameras near a coordinate.

    Every entry is re-validated through legal_guard before being emitted.
    """

    category = "cameras"
    source_id = "tourism-cam"  # default; entries can override

    def near(self, lat: float, lon: float, *, radius_km: float = 50.0) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for cam in _REGISTRY:
            dist = _haversine_km(lat, lon, cam["lat"], cam["lon"])
            if dist > radius_km:
                continue
            out.append({
                **cam,
                "distance_km": round(dist, 2),
                "fetched_at": _now_iso(),
            })
        out.sort(key=lambda r: r["distance_km"])
        return filter_records("cameras", out)

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


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
