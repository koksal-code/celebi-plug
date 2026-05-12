# CelebiPlug Install Guide

CelebiPlug is a local Flask app that records cinematic Mapbox 3D shots directly in the browser. Installation is intentionally small: Python, one Flask dependency, and a Mapbox public token.

No FFmpeg, backend renderer, account system, or secret token is required.

## Requirements

- macOS, Linux, or Windows
- Python 3.10 or newer
- A modern Chromium-based browser (134+) or Safari 16+ is recommended — these record directly to `.mp4` (H.264). Older browsers fall back to `.webm`.
- A Mapbox public access token that starts with `pk.`

Optional:

- `ffmpeg` only if you need to convert a `.webm` fallback take to `.mp4` later. Not needed on modern Chromium / Safari, which already write `.mp4` natively.

## 1. Get the project

```bash
git clone https://github.com/koksal-code/celebi-plug.git
cd celebi-plug
```

If you already have the repository, open a terminal in the project root:

```bash
cd celebi-plug
```

## 2. Create a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

The project currently installs only Flask.

## 4. Start the studio

```bash
python3 app.py
```

Open the local app:

```text
http://127.0.0.1:5001
```

The Flask server binds to `127.0.0.1` on port `5001`.

## 5. Add a Mapbox public token

CelebiPlug uses Mapbox GL JS v3 for satellite imagery, terrain, and 3D buildings. The token must start with `pk.` and is stored only in your browser under `localStorage` — never sent to the server.

**Agent / chat-native path (recommended):** the agent collects the token in chat and writes it to `.env` once — the welcome screen is skipped on every subsequent open:

```bash
echo 'MAPBOX_TOKEN=pk.eyJ1...' > /path/to/celebi-plug/.env
```

**Manual path:** open `http://127.0.0.1:5001`, go to `https://account.mapbox.com` → Access tokens → copy the default public token, then paste it into the CelebiPlug welcome screen.

Use only a public token:

```text
pk.eyJ1Ijoi...
```

Do not use a secret token:

```text
sk....
```

Secret tokens are not browser-safe and CelebiPlug does not need them.

## 6. Pick a target and record

After the studio opens, the left rail has four source tabs — pick whichever fits the input you have:

- **File** — drop or select a `.geojson` / `.json`.
- **Search** — type a place name; Mapbox geocoder resolves it and auto-tunes the radius.
- **Pin** — click anywhere on the map (auto-armed when the tab is active) or paste `lat, lon[, radius]`.
- **Box** — drag a rectangle on the map.

For Search / Pin / Box, four amber corner handles appear on the synthetic square — drag any corner to resize without re-running the input. Then:

1. Pick an aspect ratio (Pilot is the only visible preset).
2. (Optional) Mark up to two nearby POIs from the left-rail list.
3. Preview the move — preview is a single toggle button (click again to stop).
4. Record. The result modal pops with the take auto-playing.
5. **Download**, or **+ With POIs** (re-record 60s with the closest 2 POIs), or **No POI · 36s** (re-record sparse).

Downloaded files are named:

```text
celebi-plug-showcase-2026-05-11T12-00-00-000Z.mp4
```

The extension is `.mp4` on modern Chromium / Safari (H.264 directly from MediaRecorder), `.webm` on browsers without an H.264 encoder (e.g. Firefox). No conversion step runs in either case.

## Agent autopilot (one-shot from a terminal)

Once the token is saved in the browser, an agent can drive a full take without clicking. From any terminal:

```bash
open "http://127.0.0.1:5001/?q=Sultanahmet+Camii&aspect=9-16&poi=auto&autostart=1"
# ~60–70 s later, find the file (.mp4 on modern Chromium / Safari, .webm otherwise):
ls -t ~/Downloads/celebi-plug-* | head -1
```

### VPS / headless install (Docker)

If you don't have a local browser — Linux VPS, Codespaces, CI runner — run the Docker image. It bundles Chromium + Xvfb + Playwright and exposes a `/record` endpoint that returns the recorded file directly (`.mp4` when H.264 is available, `.webm` fallback otherwise):

```bash
git clone https://github.com/koksal-code/celebi-plug
cd celebi-plug

echo 'MAPBOX_TOKEN=pk.eyJ1...' > .env       # one-time token write
docker compose up -d                         # builds once (~5 min), then daemonizes

curl -OJ 'http://127.0.0.1:5001/record?q=Ayasofya+Camii&aspect=16-9&poi=auto'
```

Query params on `/record` mirror the autopilot URL (`q`/`lat`/`lon`/`radius`/`preset`/`aspect`/`poi`) — only `autostart` is implicit (`/record` always records). Response is a streamed recording with `Content-Disposition: attachment`; use `curl -OJ` so the server-provided `.mp4` / `.webm` extension is preserved.

The container binds to `127.0.0.1:5001` only, so `/record` is not reachable from the network. A 60s shot takes ~80–120s wall-clock under software WebGL (no GPU); 36s sparse mode (`poi=skip`) finishes ~50–70s.

Mac/PC users with a local browser do **not** need Docker — the in-browser autopilot flow above is faster and uses your GPU.

### Chat-native install (no welcome screen at all)

If you want a fully chat-native flow — user never opens the studio UI to enter the token — the agent can persist the `pk.` token directly in a local `.env` file:

```bash
echo 'MAPBOX_TOKEN=pk.eyJ1...' > /path/to/celebi-plug/.env
```

`app.py` reads `MAPBOX_TOKEN` from `.env` on every render, injects it into the page, and `script.js` seeds `localStorage` from it. The welcome screen is skipped on the very first open. `.env` is `.gitignored` — the token never leaves the user's machine, and there is no server endpoint that accepts tokens over the network.

Alternative for agents that don't have shell access to the celebi-plug directory: preload via the URL hash fragment instead. Hash fragments are **never sent to the Flask server**:

```bash
open "http://127.0.0.1:5001/?q=Sultanahmet&aspect=9-16&poi=auto&autostart=1#token=pk.XXX"
```

The page reads `#token=…`, writes it to `localStorage`, and strips it from the URL. On subsequent calls, omit the hash — the token is already saved. Only public tokens (`pk.`) are accepted in either path.

Full deep-link reference (`q`/`lat`/`lon`/`radius`/`preset`/`aspect`/`poi`/`autostart`) and the in-page `window.celebiPlug` JS API are documented in [`SKILL.md`](SKILL.md).

## Optional: Convert WebM to MP4

Usually unnecessary — on Chromium 134+ and Safari the take is already `.mp4`. If you ended up on the `.webm` fallback path (Firefox) and another platform requires MP4, convert it locally:

```bash
ffmpeg -i celebi-plug-pilot-*.webm \
  -c:v libx264 \
  -crf 18 \
  -preset slow \
  -pix_fmt yuv420p \
  output.mp4
```

## Verification

With the virtual environment active, verify the Python entry point:

```bash
python3 -m py_compile app.py
```

Then start the server:

```bash
python3 app.py
```

In a second terminal, check the page headers:

```bash
curl -I http://127.0.0.1:5001
```

You should see an HTTP `200` response from Flask.

## Troubleshooting

### `Address already in use`

Another process is using port `5001`. Stop the old server, or find it with:

```bash
lsof -i :5001
```

### Token is rejected

Make sure the token starts with `pk.`. Tokens starting with `sk.` are secret tokens and should not be used in the browser.

To clear a saved token, open the browser console on the CelebiPlug page and run:

```js
localStorage.removeItem("celebi-plug_mapbox_token");
location.reload();
```

### Map stays blank

Check that:

- The browser can reach `api.mapbox.com`.
- The Mapbox token is active.
- WebGL is enabled in the browser.
- Any ad blocker or privacy extension is not blocking Mapbox resources.

### Recording is unavailable

CelebiPlug records with the browser `MediaRecorder` API and `canvas.captureStream(30)`. Modern Chromium (134+) and Safari 16+ encode straight to `.mp4` (H.264); older browsers fall back to `.webm` (VP9). If neither codec is exposed (very old browser, missing WebGL), recording is unavailable — use a current Chromium-based browser.

### GeoJSON does not appear

CelebiPlug supports `FeatureCollection`, `Feature`, `Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon`, and `GeometryCollection`. Confirm the file is valid JSON and contains coordinates in `[longitude, latitude]` order.

## Uninstall

Stop the Flask server, then remove the virtual environment if you no longer need it:

```bash
rm -rf .venv
```

To remove browser-stored CelebiPlug settings, clear site data for `http://127.0.0.1:5001` or remove these localStorage keys from the console:

```js
localStorage.removeItem("celebi-plug_mapbox_token");
localStorage.removeItem("celebi-plug_lang");
```
