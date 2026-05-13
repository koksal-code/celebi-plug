"""Local TTS — system-builtin tools only, no pip dep.

* macOS — ``say -o file.aiff`` then ``afconvert`` → AAC in M4A container.
* Linux — ``espeak-ng -w file.wav`` if available.

Output is a small audio file the browser can ``<audio>`` and pipe through
Web Audio's ``MediaStreamDestination`` into MediaRecorder. No ffmpeg.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TtsResult:
    path: Path
    mime: str


def is_available() -> bool:
    return _engine() is not None


def _engine() -> str | None:
    if shutil.which("say") and shutil.which("afconvert"):
        return "macos"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "linux"
    return None


def _pick_voice(lang: str | None) -> str | None:
    """Pick a sensible default voice for macOS ``say``."""
    if not lang:
        return None
    lang = lang.lower()
    if lang.startswith("tr"):
        return "Yelda"
    if lang.startswith("de"):
        return "Anna"
    if lang.startswith("en"):
        return "Samantha"
    return None


def synthesize(text: str, *, lang: str | None = "tr", rate: int = 180) -> TtsResult | None:
    text = (text or "").strip()
    if not text:
        return None
    engine = _engine()
    if engine == "macos":
        return _macos_say(text, lang=lang, rate=rate)
    if engine == "linux":
        return _linux_espeak(text, lang=lang, rate=rate)
    return None


def _macos_say(text: str, *, lang: str | None, rate: int) -> TtsResult | None:
    voice = _pick_voice(lang)
    fd_aiff, aiff_path = tempfile.mkstemp(prefix="celebi-narr-", suffix=".aiff")
    os.close(fd_aiff)
    cmd = ["say", "-o", aiff_path, "-r", str(rate)]
    if voice:
        cmd += ["-v", voice]
    cmd += ["--", text]
    if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        Path(aiff_path).unlink(missing_ok=True)
        return None
    m4a_path = aiff_path.replace(".aiff", ".m4a")
    afc = subprocess.run(
        ["afconvert", "-f", "m4af", "-d", "aac", aiff_path, m4a_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(aiff_path).unlink(missing_ok=True)
    if afc.returncode != 0 or not Path(m4a_path).exists():
        return None
    return TtsResult(path=Path(m4a_path), mime="audio/mp4")


def _linux_espeak(text: str, *, lang: str | None, rate: int) -> TtsResult | None:
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary:
        return None
    fd_wav, wav_path = tempfile.mkstemp(prefix="celebi-narr-", suffix=".wav")
    os.close(fd_wav)
    cmd = [binary, "-w", wav_path, "-s", str(rate)]
    if lang:
        cmd += ["-v", lang.split("-")[0].lower()]
    cmd += ["--", text]
    if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        Path(wav_path).unlink(missing_ok=True)
        return None
    return TtsResult(path=Path(wav_path), mime="audio/wav")
