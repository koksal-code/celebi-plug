"""Wildfire provider — NASA FIRMS (active fire CSV feeds)."""

from __future__ import annotations

import csv
import io
import os
from typing import Any

from utils.http import HttpError, get_text

from .base import BaseProvider


class NasaFirmsProvider(BaseProvider):
    category = "wildfire"
    source_id = "nasa-firms"

    # Public mirror — no token. The MAP_KEY API gives broader access but
    # the static CSVs are sufficient for the default last-24h heatmap.
    CSV_24H = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv"

    def __init__(self, map_key: str | None = None) -> None:
        super().__init__()
        self.map_key = (map_key or os.environ.get("FIRMS_MAP_KEY") or "").strip()

    def active(
        self,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        limit: int = 500,
        min_confidence: int = 30,
    ) -> list[dict[str, Any]]:
        """Return active fires from the global 24h MODIS feed.

        ``bbox`` is ``(west, south, east, north)``. If provided, results
        are filtered locally — keeps the network call to a single download.
        """
        try:
            body = get_text(self.CSV_24H, timeout=20.0)
        except HttpError:
            return []
        reader = csv.DictReader(io.StringIO(body))
        west = south = east = north = None
        if bbox:
            west, south, east, north = bbox
        out: list[dict[str, Any]] = []
        for row in reader:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (KeyError, ValueError):
                continue
            conf = row.get("confidence")
            try:
                conf_v = int(float(conf)) if conf not in (None, "") else 0
            except ValueError:
                conf_v = 0
            if conf_v < min_confidence:
                continue
            if bbox and not (west <= lon <= east and south <= lat <= north):
                continue
            out.append({
                "lat": lat,
                "lon": lon,
                "brightness_k": _float(row.get("brightness")),
                "frp_mw": _float(row.get("frp")),
                "confidence": conf_v,
                "acq_date": row.get("acq_date"),
                "acq_time": row.get("acq_time"),
                "satellite": row.get("satellite"),
                "source": self.source_id,
            })
            if len(out) >= limit:
                break
        return out


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
