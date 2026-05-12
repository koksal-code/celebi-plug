import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, render_template, request, send_file

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# /record serializes Chromium spawns — Xvfb display is single-tenant
# and concurrent renders trash each other's frame timing.
_render_lock = threading.Lock()
_record_query_keys = {"q", "lat", "lon", "radius", "preset", "aspect", "poi"}
_recording_mimetypes = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def load_env_token() -> str:
    """Resolve the user's Mapbox pk. token. Two sources, in priority:
       1. MAPBOX_TOKEN env var (Docker / VPS path — docker-compose
          loads it via env_file).
       2. .env file next to app.py (Mac / PC chat-native path — an
          agent writes it once and the welcome screen is skipped).
    Only pk. tokens are honored."""
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


def render_backend_available() -> bool:
    """The /record endpoint only works when Playwright + xvfb-run are
    installed (i.e. the Docker image). On a Mac dev install neither is
    present and the endpoint returns 503 with guidance."""
    if shutil.which("xvfb-run") is None:
        return False
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def make_safe_download_piece(value: str, fallback: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in {"-", "_", "."} else "_"
        for ch in (value or "").strip()
    )
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def recording_mimetype(path: Path) -> str:
    return _recording_mimetypes.get(path.suffix.lower(), "application/octet-stream")


def transcode_webm_to_mp4(input_path: Path) -> Path:
    """Convert a WebM capture to H.264 MP4 for downstream compatibility."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin is None:
        raise RuntimeError(
            "ffmpeg not found in container. Rebuild Docker image and try again:\n"
            "  docker compose up -d --build\n"
        )

    output_path = input_path.with_suffix(".mp4")
    result = subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ],
        capture_output=True,
        timeout=180,
    )
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        log = (result.stderr or result.stdout or b"").decode("utf-8", "replace")
        raise RuntimeError(f"ffmpeg transcode failed:\n\n{log}\n")
    return output_path


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return render_template("index.html", env_token=load_env_token())


@app.route("/record")
def record():
    """Headless recording for VPS users. Spawns Chromium under Xvfb,
    points it at the autopilot URL, captures WebM in-browser, then
    transcodes to MP4 before streaming the file back.

    Mac/PC users skip this entirely — they record in their own browser
    via the autopilot URL at /."""
    if not render_backend_available():
        return (
            "render backend unavailable: this endpoint requires the Docker "
            "image (Playwright + Xvfb). On a local Mac/PC, open the autopilot "
            "URL in your own browser instead — see README.md.\n",
            503,
        )

    if not load_env_token():
        return (
            "no MAPBOX_TOKEN in .env. Write one with:\n"
            "  echo 'MAPBOX_TOKEN=pk.eyJ1...' > .env\n",
            400,
        )

    forwarded = {k: v for k, v in request.args.items() if k in _record_query_keys}
    forwarded["autostart"] = "1"
    forwarded["record_mime"] = "webm"
    query = urlencode(forwarded)
    internal_port = os.environ.get("PORT") or request.environ.get("SERVER_PORT") or "5001"
    autopilot_url = f"http://127.0.0.1:{internal_port}/?{query}"

    tmp_dir = Path(tempfile.mkdtemp(prefix="celebi-record-"))
    output_stem = tmp_dir / "celebi-plug"

    try:
        with _render_lock:
            result = subprocess.run(
                [
                    "xvfb-run", "-a",
                    "--server-args=-screen 0 1920x1080x24",
                    "python3", str(Path(__file__).parent / "render_worker.py"),
                    autopilot_url, str(output_stem),
                ],
                capture_output=True,
                timeout=240,
            )
        output_paths = sorted(
            p for p in tmp_dir.glob("celebi-plug.*")
            if p.suffix.lower() in _recording_mimetypes
        )
        if result.returncode != 0 or not output_paths:
            log = (result.stderr or result.stdout or b"").decode("utf-8", "replace")
            return (
                f"record worker failed (exit {result.returncode}):\n\n{log}\n",
                500,
            )
        output_path = output_paths[-1]
        if output_path.suffix.lower() == ".webm":
            try:
                output_path = transcode_webm_to_mp4(output_path)
            except RuntimeError as exc:
                return str(exc), 500

        preset = make_safe_download_piece(forwarded.get("preset", "showcase"), "showcase")
        subject = make_safe_download_piece(forwarded.get("q", "shot"), "shot")
        download_name = f"celebi-plug-{preset}-{subject}{output_path.suffix.lower()}"
        return send_file(
            output_path,
            mimetype=recording_mimetype(output_path),
            as_attachment=True,
            download_name=download_name,
        )
    except subprocess.TimeoutExpired:
        return "record worker timed out after 240s\n", 504
    finally:
        # send_file streams the body after this function returns, so tmp
        # dirs are swept opportunistically by _cleanup_tmpdirs below.
        pass


@app.teardown_request
def _cleanup_tmpdirs(_exc):
    # Best-effort: tmp dirs accumulate; sweep anything older than an hour.
    import time
    tmp_root = Path(tempfile.gettempdir())
    now = time.time()
    for entry in tmp_root.glob("celebi-record-*"):
        try:
            if entry.is_dir() and now - entry.stat().st_mtime > 3600:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            pass


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", host=host, port=port)
