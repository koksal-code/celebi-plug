import os
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


def load_env_token() -> str:
    """Resolve MAPBOX_TOKEN from env var or local .env (pk.* only)."""
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
def record_disabled():
    return (
        "local-only build: /record is disabled.\n"
        "Use a local GUI browser at http://127.0.0.1:5001 and record in-studio.\n",
        410,
    )


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", host=host, port=port)
