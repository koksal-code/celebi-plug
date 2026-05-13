"""Earthquake providers — AFAD, Kandilli, USGS fallback."""

from __future__ import annotations

import re
from typing import Any

from utils.http import HttpError, get_json, get_text

from .base import BaseProvider


class AfadProvider(BaseProvider):
    category = "earthquake"
    source_id = "afad"

    BASE = "https://deprem.afad.gov.tr/apiv2/event/filter"

    def recent(self, *, limit: int = 50, min_magnitude: float = 0.0) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=3)
        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "limit": min(limit, 500),
        }
        try:
            data = get_json(self.BASE, params=params, timeout=8.0)
        except HttpError:
            return []
        out: list[dict[str, Any]] = []
        for item in data if isinstance(data, list) else (data.get("result") or []):
            mag = _float(item.get("magnitude") or item.get("mag"))
            if mag is None or mag < min_magnitude:
                continue
            out.append({
                "magnitude": mag,
                "depth_km": _float(item.get("depth")),
                "lat": _float(item.get("latitude") or item.get("lat")),
                "lon": _float(item.get("longitude") or item.get("lon")),
                "location": item.get("location") or item.get("region"),
                "time": item.get("date") or item.get("time"),
                "source": self.source_id,
            })
        out.sort(key=lambda r: r.get("time") or "", reverse=True)
        return out[:limit]


class KandilliProvider(BaseProvider):
    """Boğaziçi Üniversitesi Kandilli Rasathanesi public list.

    The institutional page is fixed-width text; we parse defensively.
    """

    category = "earthquake"
    source_id = "kandilli"

    URL = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
    _LINE = re.compile(
        r"^(?P<date>\d{4}\.\d{2}\.\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
        r"(?P<lat>\d+\.\d+)\s+(?P<lon>\d+\.\d+)\s+"
        r"(?P<depth>\d+\.\d+)\s+(?:-\.-|\d+\.\d+)\s+"
        r"(?P<md>-\.-|\d+\.\d+)\s+(?P<ml>-\.-|\d+\.\d+)\s+(?P<mw>-\.-|\d+\.\d+)\s+"
        r"(?P<region>.+?)\s+(?:Ilksel|İlksel|REVIZE.*)?$"
    )

    def recent(self, *, limit: int = 50, min_magnitude: float = 0.0) -> list[dict[str, Any]]:
        try:
            body = get_text(self.URL, timeout=8.0)
        except HttpError:
            return []
        out: list[dict[str, Any]] = []
        for raw in body.splitlines():
            line = raw.strip()
            match = self._LINE.match(line)
            if not match:
                continue
            ml = _float(match.group("ml"))
            mw = _float(match.group("mw"))
            md = _float(match.group("md"))
            mag = mw or ml or md
            if mag is None or mag < min_magnitude:
                continue
            out.append({
                "magnitude": mag,
                "depth_km": _float(match.group("depth")),
                "lat": _float(match.group("lat")),
                "lon": _float(match.group("lon")),
                "location": match.group("region").strip(),
                "time": f"{match.group('date').replace('.', '-')}T{match.group('time')}",
                "source": self.source_id,
            })
            if len(out) >= limit:
                break
        return out


class UsgsProvider(BaseProvider):
    """USGS GeoJSON feed — global coverage fallback."""

    category = "earthquake"
    source_id = "usgs"

    URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

    def recent(self, *, limit: int = 50, min_magnitude: float = 0.0) -> list[dict[str, Any]]:
        try:
            data = get_json(self.URL, timeout=8.0)
        except HttpError:
            return []
        out: list[dict[str, Any]] = []
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or [None, None, None]
            mag = _float(props.get("mag"))
            if mag is None or mag < min_magnitude:
                continue
            out.append({
                "magnitude": mag,
                "depth_km": _float(coords[2]) if len(coords) >= 3 else None,
                "lat": _float(coords[1]) if len(coords) >= 2 else None,
                "lon": _float(coords[0]) if len(coords) >= 1 else None,
                "location": props.get("place"),
                "time": props.get("time"),
                "source": self.source_id,
            })
        out.sort(key=lambda r: r.get("time") or 0, reverse=True)
        return out[:limit]


def _float(value: Any) -> float | None:
    if value in (None, "", "-.-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
