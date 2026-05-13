"""Local TTS — system-builtin tools only, no pip dep.

* macOS — ``say -o file.aiff`` then ``afconvert`` → AAC in M4A container.
* Linux — ``espeak-ng -w file.wav`` if available.

Default voice is the best available **male** neural voice per language.
Override with ``CELEBI_TTS_VOICE=<voice-name>`` environment variable.

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


# Male neural voices available on macOS Ventura+ (Sonoma preferred).
# Turkish has no male system voice — Eddy (en_US neural) reads Turkish
# with natural male quality; set CELEBI_TTS_VOICE=Yelda for native female.
_MALE_NEURAL_VOICES: dict[str, str] = {
    "tr": "Eddy (İngilizce (ABD))",    # Neural male — best quality for TR
    "de": "Reed (Almanca (Almanya))",   # Neural male German
    "en": "Eddy (İngilizce (ABD))",    # Neural male English
}
_FALLBACK_VOICES: dict[str, str] = {
    "tr": "Yelda",      # Native Turkish (female) fallback
    "de": "Markus",
    "en": "Daniel",
}

# Slightly slower than default — neural voices sound best at ~155 wpm
_DEFAULT_RATE = 155


def _pick_voice(lang: str | None) -> str:
    """Return the best available male voice for *lang*."""
    # Explicit env override takes priority
    override = os.environ.get("CELEBI_TTS_VOICE", "").strip()
    if override:
        return override

    lang_key = (lang or "en").lower()[:2]
    preferred = _MALE_NEURAL_VOICES.get(lang_key, "Eddy (İngilizce (ABD))")

    # Probe that the voice actually exists (quick dry-run)
    if _voice_exists(preferred):
        return preferred

    fallback = _FALLBACK_VOICES.get(lang_key, "Daniel")
    return fallback


def _voice_exists(voice: str) -> bool:
    """Return True if ``say -v <voice>`` exits 0 on a trivial string."""
    try:
        result = subprocess.run(
            ["say", "-v", voice, "--output-file", "/dev/null", "test"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def synthesize(
    text: str,
    *,
    lang: str | None = "tr",
    rate: int | None = None,
) -> TtsResult | None:
    text = (text or "").strip()
    if not text:
        return None
    r = rate if rate is not None else _DEFAULT_RATE
    engine = _engine()
    if engine == "macos":
        return _macos_say(text, lang=lang, rate=r)
    if engine == "linux":
        return _linux_espeak(text, lang=lang, rate=r)
    return None


def _macos_say(text: str, *, lang: str | None, rate: int) -> TtsResult | None:
    voice = _pick_voice(lang)
    fd_aiff, aiff_path = tempfile.mkstemp(prefix="celebi-narr-", suffix=".aiff")
    os.close(fd_aiff)
    cmd = ["say", "-o", aiff_path, "-r", str(rate), "-v", voice, "--", text]
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
