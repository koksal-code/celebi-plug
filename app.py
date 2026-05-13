import os
from ipaddress import ip_address, ip_network
from pathlib import Path

from flask import Flask, abort, render_template, request

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

LOCAL_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("::1/128"),
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_local_request() -> bool:
    """Allow only loopback browser requests."""
    raw_host = (request.host or "").lower()
    if raw_host.startswith("["):
        host = raw_host.partition("]")[0].strip("[]")
    else:
        host = raw_host.split(":", 1)[0]
    if host not in LOCAL_HOSTS:
        return False
    try:
        remote = ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return any(remote in network for network in LOCAL_NETWORKS)


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


@app.before_request
def guard_local_only():
    if not is_local_request():
        abort(403)


@app.route("/")
def index():
    return render_template("index.html", env_token=load_env_token())


@app.route("/record")
def record_disabled():
    return (
        "server-side /record is disabled.\n"
        "Use a same-machine GUI browser at http://127.0.0.1:5001; agents can record through the studio autopilot/API.\n",
        410,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", host="127.0.0.1", port=port)
