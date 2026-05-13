"""Narration text builder + TTS bytes.

The browser fetches ``/api/narration?q=<place>&auto=1`` (or with
explicit ``&text=...``) and mixes the resulting audio into MediaRecorder
via Web Audio. No ffmpeg merge needed — the recording lays the audio
track directly into the .mp4 container alongside H.264 video.
"""

from __future__ import annotations

from typing import Any

from . import live as live_mod


def auto_text_for(place: str, *, lang: str = "tr") -> str:
    """Generate a ~10 second narration script for ``place``."""
    try:
        bundle = live_mod.snapshot(place, marine=False, radius_km=50.0)
    except ValueError:
        return _fallback(place, lang)
    return _compose(bundle, lang=lang)


def _fallback(place: str, lang: str) -> str:
    if lang.startswith("tr"):
        return f"Çelebi. {place}. Cinematic uçuş başlıyor."
    if lang.startswith("de"):
        return f"Celebi. {place}. Cinematic-Flug startet."
    return f"Celebi. {place}. Cinematic flight engaging."


def _compose(b: dict[str, Any], *, lang: str) -> str:
    name = (b.get("place") or "").split(",")[0].strip() or "the area"
    w = b.get("weather") or {}
    temp = w.get("temperature_c")
    wind = w.get("wind_kmh")
    fires = b.get("wildfires_nearby") or 0
    cams = b.get("cameras") or []

    if lang.startswith("tr"):
        parts = [f"Çelebi {name} üstünde."]
        if temp is not None:
            parts.append(f"Sıcaklık {round(temp)} derece.")
        if wind is not None:
            parts.append(f"Rüzgâr {round(wind)} kilometre saat.")
        if fires:
            parts.append(f"Yakında {fires} aktif termal nokta var.")
        if cams:
            parts.append(f"Canlı kamera: {cams[0]['name']}.")
        parts.append("Cinematic uçuş başlıyor.")
        return " ".join(parts)

    if lang.startswith("de"):
        parts = [f"Celebi über {name}."]
        if temp is not None:
            parts.append(f"Temperatur {round(temp)} Grad.")
        if wind is not None:
            parts.append(f"Wind {round(wind)} Kilometer pro Stunde.")
        if fires:
            parts.append(f"In der Nähe {fires} aktive Hitzepunkte.")
        if cams:
            parts.append(f"Live-Kamera: {cams[0]['name']}.")
        parts.append("Cinematic-Flug startet.")
        return " ".join(parts)

    parts = [f"Celebi over {name}."]
    if temp is not None:
        parts.append(f"Temperature {round(temp)} degrees.")
    if wind is not None:
        parts.append(f"Wind {round(wind)} kilometres per hour.")
    if fires:
        parts.append(f"{fires} active thermal anomalies nearby.")
    if cams:
        parts.append(f"Live camera: {cams[0]['name']}.")
    parts.append("Cinematic flight engaging.")
    return " ".join(parts)
