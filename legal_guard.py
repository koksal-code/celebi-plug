"""Central legal/ethics guard for CelebiPlug data sources.

Every provider must declare itself to legal_guard before returning data.
The guard rejects:
  - military / restricted-airspace aircraft
  - private "blocked" aircraft (PIA / LADD opt-outs surface as `special`)
  - MOBESE / KGYS / private surveillance cameras
  - non-public scraping targets

Modules call ``ensure_source(category, source_id)`` once per provider
instance and ``filter_record(category, record)`` per emitted record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class SourcePolicy:
    """Whitelist entry for a data source."""

    source_id: str
    license: str  # e.g. "CC-BY", "ODbL", "public-domain", "tos-compliant"
    public: bool  # data must be publicly published, not scraped


# Whitelist — keep tight. Adding a source = adding a row here.
_WHITELIST: dict[str, dict[str, SourcePolicy]] = {
    "weather": {
        "open-meteo": SourcePolicy("open-meteo", "CC-BY-4.0", True),
        "openweather": SourcePolicy("openweather", "tos-compliant", True),
    },
    "news": {
        "rss": SourcePolicy("rss", "publisher-rss-feed", True),
        "newsapi": SourcePolicy("newsapi", "tos-compliant", True),
    },
    "aircraft": {
        "opensky": SourcePolicy("opensky", "CC-BY-4.0", True),
        "adsb-lol": SourcePolicy("adsb-lol", "ODbL", True),
    },
    "earthquake": {
        "afad": SourcePolicy("afad", "public-domain", True),
        "kandilli": SourcePolicy("kandilli", "public-domain", True),
        "usgs": SourcePolicy("usgs", "public-domain", True),
    },
    "wildfire": {
        "nasa-firms": SourcePolicy("nasa-firms", "public-domain", True),
    },
    "cameras": {
        # Public, official, licensed cameras only. Adding a row here is an
        # explicit assertion that the camera is operated by a tourism /
        # municipality / national-park body for public viewing.
        "kgm-official": SourcePolicy("kgm-official", "public-traffic-camera", True),
        "tourism-cam": SourcePolicy("tourism-cam", "tourism-public-feed", True),
        "national-park": SourcePolicy("national-park", "park-authority-feed", True),
        "osm-webcam": SourcePolicy("osm-webcam", "ODbL-1.0", True),
        "windy-webcams": SourcePolicy("windy-webcams", "tos-compliant", True),
        "youtube-live": SourcePolicy("youtube-live", "platform-tos-compliant", True),
    },
}


# Forbidden tokens — any source whose id or name matches these is rejected
# even if a contributor accidentally adds it to the whitelist.
_FORBIDDEN_TOKENS = {
    "mobese",
    "kgys",
    "guvenlik-kamera",
    "surveillance",
    "private-cctv",
    "police-cam",
    "law-enforcement",
}


# Military / restricted aircraft categories — OpenSky and ADS-B-lol expose
# these via icao24 ranges, callsign patterns, or operator tags. We reject by
# callsign prefix as a defensive measure; the provider layer should also
# refuse to expose private-blocked records.
_MILITARY_CALLSIGN_PREFIXES = (
    "RCH",   # USAF Air Mobility Command
    "PAT",   # US Army
    "BLUE",  # US Air Force One callsign family
    "FORCE", # USAF demo
    "DOOM",  # B-52 ops
    "REACH",
    "SAM",   # Special Air Mission
    "AF1",
    "AF2",
    "GAF",   # German AF
    "TAF",   # Turkish Air Force
    "NATO",
    "TURAF",
    "MAGMA",
    "PEACH",
)


class LegalGuardError(RuntimeError):
    """Raised when a provider attempts to surface non-compliant data."""


def ensure_source(category: str, source_id: str) -> SourcePolicy:
    """Validate a (category, source_id) pair against the whitelist."""
    src_norm = (source_id or "").strip().lower()
    if not src_norm:
        raise LegalGuardError("source_id is required")
    for token in _FORBIDDEN_TOKENS:
        if token in src_norm:
            raise LegalGuardError(f"forbidden source token: {token}")
    cat = _WHITELIST.get(category)
    if not cat:
        raise LegalGuardError(f"unknown category: {category}")
    policy = cat.get(src_norm)
    if not policy:
        raise LegalGuardError(
            f"source '{src_norm}' is not on the whitelist for '{category}'. "
            f"Allowed: {sorted(cat.keys())}"
        )
    return policy


def list_sources(category: str) -> list[str]:
    return sorted((_WHITELIST.get(category) or {}).keys())


def is_military_callsign(callsign: str | None) -> bool:
    if not callsign:
        return False
    cs = callsign.strip().upper()
    return any(cs.startswith(prefix) for prefix in _MILITARY_CALLSIGN_PREFIXES)


def filter_record(category: str, record: Mapping) -> Mapping | None:
    """Per-record filter. Returns ``None`` if the record must be dropped."""
    if category == "aircraft":
        callsign = (record.get("callsign") or "").strip()
        if is_military_callsign(callsign):
            return None
        if record.get("special") in {"military", "blocked", "ladd", "pia"}:
            return None
        if record.get("category") in {"military", "restricted"}:
            return None
    if category == "cameras":
        name = (record.get("name") or "").lower()
        op = (record.get("operator") or "").lower()
        text = f"{name} {op}"
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                return None
    return record


def filter_records(category: str, records: Iterable[Mapping]) -> list[Mapping]:
    out: list[Mapping] = []
    for rec in records:
        kept = filter_record(category, rec)
        if kept is not None:
            out.append(dict(kept))
    return out
