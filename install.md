# CelebiPlug Install Guide

CelebiPlug is a local Flask app that records cinematic Mapbox 3D shots directly in the browser **and** exposes a small geo-intelligence API and CLI (weather, news, aircraft, earthquakes, wildfires, public cameras). Installation is intentionally small: Python, one Flask dependency, and a Mapbox public token for the recording studio.

No FFmpeg, backend renderer, account system, secret token, or extra Python package is required. The geo-intelligence modules use only the standard library on top of free public data sources — every additional token is optional.

## Requirements

- macOS, Linux, or Windows
- Python 3.10 or newer
- A GUI browser with WebGL/GPU acceleration and MP4/H.264 MediaRecorder support
- A Mapbox public access token that starts with `pk.`

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

The output is always `.mp4`. If the browser cannot record MP4/H.264, the studio disables recording instead of producing a fallback file.

## Agent autopilot (one-shot from a terminal)

Once the token is saved in the browser, an agent can drive a full take without clicking. From any terminal:

```bash
open "http://127.0.0.1:5001/?q=<URL_ENCODED_PLACE>&aspect=9-16&poi=skip&autostart=1"
# ~60–70 s later, find the MP4 file:
ls -t ~/Downloads/celebi-plug-* | head -1
```

Keep the recording browser visible. If an agent launches Chrome, use a foreground window or disable background throttling; otherwise browsers may produce a too-short MP4. Always verify duration before reporting success.

### GUI runtime

CelebiPlug records only when the runtime has a GUI browser, GPU/WebGL, and MP4/H.264 support.

- Start `python3 app.py` and use `http://127.0.0.1:5001`.
- If GUI/GPU/MP4 checks fail, the agent should say: `GPU/GUI yok, Çelebi uçuş yapamaz. Kurulumu iptal ediyorum; kurulumdan kalan dosyaları sileyim mi?`
- Cleanup should only happen after the user confirms.
- Agents record through the studio, autopilot URL, or `window.celebiPlug.record()`.

### Chat-native install (no welcome screen at all)

If you want a fully chat-native flow — user never opens the studio UI to enter the token — the agent can persist the `pk.` token directly in a local `.env` file:

```bash
echo 'MAPBOX_TOKEN=pk.eyJ1...' > /path/to/celebi-plug/.env
```

`app.py` reads `MAPBOX_TOKEN` from `.env` on every render, injects it into the page, and `script.js` seeds `localStorage` from it. The welcome screen is skipped on the very first open. `.env` is `.gitignored` — the token never leaves the user's machine, and there is no server endpoint that accepts tokens over the network.

Alternative for agents that don't have shell access to the celebi-plug directory: preload via the URL hash fragment instead. Hash fragments are **never sent to the Flask server**:

```bash
open "http://127.0.0.1:5001/?q=<URL_ENCODED_PLACE>&aspect=9-16&poi=skip&autostart=1#token=pk.XXX"
```

The page reads `#token=…`, writes it to `localStorage`, and strips it from the URL. On subsequent calls, omit the hash — the token is already saved. Only public tokens (`pk.`) are accepted in either path.

Full deep-link reference (`q`/`lat`/`lon`/`radius`/`preset`/`aspect`/`poi`/`autostart`) and the in-page `window.celebiPlug` JS API are documented in [`SKILL.md`](SKILL.md).

## Geo-intelligence modules (optional, all token-free by default)

When the Flask process is running, six side modules become available alongside the studio. They share the same `127.0.0.1:5001` port and only accept loopback requests — nothing is exposed to the network.

```bash
# All endpoints return JSON.
curl 'http://127.0.0.1:5001/health'
curl 'http://127.0.0.1:5001/api/weather?q=Fethiye'
curl 'http://127.0.0.1:5001/api/news?q=Antalya'
curl 'http://127.0.0.1:5001/api/aircraft?callsign=TK1923'
curl 'http://127.0.0.1:5001/api/earthquakes?min=2'
curl 'http://127.0.0.1:5001/api/wildfires?q=Manavgat'
curl 'http://127.0.0.1:5001/api/cameras?q=Fethiye'
```

The repo also ships a `./celebi` bash wrapper that calls the same modules from the terminal:

```bash
./celebi weather "Fethiye"
./celebi news "Fethiye"
./celebi aircraft TK1923
./celebi earthquake --min 3
./celebi wildfire --place "Manavgat"
./celebi cameras "Fethiye"

# Single-frame artifact delivery
./celebi snap-aircraft TK1923          # PNG: satellite + pin + info card
./celebi snap-camera "Fethiye"         # PNG: real frame if available, satellite fallback
./celebi map "Fethiye" --snapshot      # PNG: satellite still of the place

# Cinematic MP4 delivery (drives the studio autopilot, returns the path)
./celebi film "Fethiye Ölüdeniz" --aspect 9-16 --duration 36
./celebi film "Fethiye" --narrate auto # MP4 with built-in TTS narration

# Narration only (text + AAC audio file)
./celebi narrate --place "Fethiye" --lang tr
./celebi narrate "Selam Çelebi" --lang tr
```

### Optional: composite info cards on snap PNGs

Snap commands deliver a satellite still by default. Install **Pillow** to bake a CelebiPlug-style info card (callsign / altitude / speed / source) onto the same image:

```bash
pip install Pillow
```

Without Pillow, snap returns the raw PNG plus a JSON sidecar with the metadata — the chat client can lay them out side-by-side.

### Optional: narration TTS engine

`celebi narrate` and `celebi film --narrate` use whichever local TTS engine is on PATH:

- **macOS** — built-in `say` + `afconvert` produce AAC in `.m4a`. No install needed.
- **Linux** — `apt install espeak-ng` (or `espeak`) for WAV output.
- **Windows** — narration is a noop today; the recording is delivered silent.

The narration is mixed into the recording in the browser via Web Audio → MediaRecorder, so no ffmpeg is involved.

The wrapper auto-selects the project's Python (`VIRTUAL_ENV`, then `.venv/bin/python`, then `python3`). Symlink it into `~/.local/bin/` to drop the `./` prefix:

```bash
ln -s "$(pwd)/celebi" ~/.local/bin/celebi
```

Defaults are free and require no token:

| Module | Default | Optional upgrade |
|---|---|---|
| Weather | Open-Meteo | `CELEBI_WEATHER_PROVIDER=openweather` + `OPENWEATHER_API_KEY` |
| News | RSS (TRT · Hürriyet · NTV · BBC · Reuters) | `CELEBI_NEWS_PROVIDER=newsapi` + `NEWSAPI_KEY` |
| Aircraft | OpenSky anon → ADS-B.lol | `OPENSKY_USERNAME` / `OPENSKY_PASSWORD` for higher rate |
| Earthquakes | AFAD → Kandilli → USGS | `CELEBI_EARTHQUAKE_PROVIDERS=...` to reorder |
| Wildfires | NASA FIRMS 24h global CSV | `FIRMS_MAP_KEY` |
| Cameras | Curated public registry only | (add rows to [`providers/cameras.py`](providers/cameras.py)) |

Legal guard: every record is filtered through [`legal_guard.py`](legal_guard.py), which rejects MOBESE / KGYS / private surveillance cameras and military / blocked aircraft. New sources must be whitelisted there before they can surface data.

## Verification

With the virtual environment active, verify the Python entry point and the geo-intel modules:

```bash
python3 -m py_compile app.py cli.py legal_guard.py
python3 -m py_compile providers/*.py modules/*.py utils/*.py
```

Then start the server:

```bash
python3 app.py
```

In a second terminal, check the page headers and the geo-intel health probe:

```bash
curl -I http://127.0.0.1:5001
curl  http://127.0.0.1:5001/health
```

You should see an HTTP `200` response from Flask and a JSON payload listing the registered providers per module.

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

CelebiPlug records with the browser `MediaRecorder` API and `canvas.captureStream(30)`. Recording requires a GUI browser on the same machine with WebGL/GPU acceleration and MP4/H.264 encoder support. If the system check fails, use a current Chromium-based browser or Safari on a machine with GUI/GPU support.

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
