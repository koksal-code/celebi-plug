"""Earthquake module — AFAD primary, Kandilli secondary, USGS global fallback."""

from __future__ import annotations

import os
from typing import Any

from providers.earthquake import AfadProvider, KandilliProvider, UsgsProvider


def _provider_chain() -> list[str]:
    raw = (os.environ.get("CELEBI_EARTHQUAKE_PROVIDERS") or "afad,kandilli,usgs").lower()
    return [p.strip() for p in raw.split(",") if p.strip()]


_PROVIDERS = {
    "afad": AfadProvider,
    "kandilli": KandilliProvider,
    "usgs": UsgsProvider,
}


def recent(*, limit: int = 50, min_magnitude: float = 0.0) -> list[dict[str, Any]]:
    last_err: Exception | None = None
    for name in _provider_chain():
        cls = _PROVIDERS.get(name)
        if not cls:
            continue
        try:
            data = cls().recent(limit=limit, min_magnitude=min_magnitude)
            if data:
                return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    if last_err is not None:
        raise last_err
    return []
