<p align="center">
  <img src="docs/logo.png" width="120" alt="CelebiPlug logo"/>
</p>

<h1 align="center">CelebiPlug</h1>

<p align="center">
  <strong>Your pocket drone. Cinematic 3D shots + local geo-intelligence.</strong>
</p>

<p align="center">
  <a href="https://github.com/koksal-code/celebi-plug/issues">Report Bug</a>
  ·
  <a href="https://github.com/koksal-code/celebi-plug/issues">Request Feature</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Mapbox-3D-black?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/MP4-H.264-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Flask-Minimal-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge"/>
</p>

---

CelebiPlug turns any place — a search query, a GeoJSON file, a map pin, or a bounding box — into a **cinematic 3D drone-style MP4** recorded directly in your browser. Alongside the studio it ships a local **geo-intelligence API and CLI**: weather, news, live aircraft, earthquakes, wildfires, and public cameras — all with free/open-data defaults and no new server required.

```
Place → Mapbox 3D scene → Pilot preset → MediaRecorder → celebi-plug-*.mp4
                                                           12 Mbps · H.264 · 30 fps
```

---

## Quick Start

```bash
git clone https://github.com/koksal-code/celebi-plug
cd celebi-plug

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:5001` in a GUI browser with WebGL/GPU support.

**Token setup** — get a free `pk.` token at [account.mapbox.com](https://account.mapbox.com) → Access tokens. Paste it in the welcome screen, or pre-load it:

```bash
echo 'MAPBOX_TOKEN=pk.eyJ1...' > .env
```

Never use an `sk.` secret token. The token is stored only in your browser's `localStorage` and never sent to the server.

---

## Studio Features

- Mapbox satellite + 3D terrain + real-time building extrusions
- **Four input modes:** drop a GeoJSON · search a place · drop a pin · drag a bounding box
- Auto-tuned framing — radius scales from geocoder `place_type`
- Draggable corner handles to resize framing without re-running input
- **Pilot preset** — 60 s full (5 scenes, 720° rotation) or 36 s sparse (3 scenes, no POI)
- Browser-native MP4/H.264 at 12 Mbps, 30 fps — no FFmpeg
- Fade-to-black scene transitions
- Result modal — preview, download, or re-record
- Agent autopilot — drive the studio via deep-link URL or the `window.celebiPlug` JS bridge
- Opt-in TTS narration baked into the MP4 via Web Audio (no FFmpeg merge)

---

## Geo-Intelligence Modules

Six modules, all token-free by default.

| Module | Default | Optional |
|--------|---------|----------|
| Weather | Open-Meteo | OpenWeather (`OPENWEATHER_API_KEY`) |
| News | RSS (TRT · BBC · Reuters…) | NewsAPI (`NEWSAPI_KEY`) |
| Aircraft | OpenSky | ADS-B.lol |
| Earthquakes | AFAD → Kandilli → USGS | — |
| Wildfires | NASA FIRMS MODIS/VIIRS 24 h | optional `FIRMS_MAP_KEY` |
| Cameras | Local registry + OSM/Windy/YouTube discovery | `WINDY_WEBCAMS_API_KEY` · `yt-dlp` |

All data passes through `legal_guard.py`: military callsigns filtered, MOBESE/KGYS/private surveillance blocked, every source whitelisted by license.

---

## CLI

`./celebi` is a bash wrapper around `cli.py` that picks the project Python automatically.

```bash
# Geo-intel
./celebi weather "Fethiye"
./celebi weather --lat 36.65 --lon 29.12 --marine
./celebi news "Antalya" --limit 10
./celebi aircraft TK1923
./celebi aircraft --place "Fethiye" --radius-km 80
./celebi earthquake --min 3
./celebi wildfire --place "Manavgat"
./celebi cameras "Fethiye"
./celebi cameras "Fethiye" --discover       # OSM + Windy + YouTube live discovery
./celebi live "Fethiye"                     # combined bundle: weather + cameras + fires + map

# Single-frame artifacts (files, not links)
./celebi snap-aircraft TK1923               # satellite PNG + info card
./celebi snap-camera "Fethiye"              # live JPEG or satellite fallback
./celebi snap-camera "Fethiye" --discover   # discovery-enabled
./celebi snap-wildfire "Antalya"            # nearest NASA FIRMS hotspot → PNG + info card

# Cinematic MP4
./celebi film "Fethiye"
./celebi film "Fethiye" --narrate auto      # TTS narration baked in (no FFmpeg)
./celebi film "Fethiye" --aspect 9-16 --preset orbit
./celebi film --wildfire "Antalya"          # find nearest fire → fly there with auto narration
./celebi film --geojson area.geojson        # extract centroid and film that location

# Narration
./celebi narrate --place "Fethiye" --lang tr
./celebi narrate --place "Fethiye" --lang en --text-only
```

The CLI prints JSON to stdout. Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` for richer LLM-generated narration; the template builder is used as fallback with no extra dependencies.

---

## Local API

Binds to `127.0.0.1:5001`, loopback-only.

```
GET /health
GET /api/weather?q=Fethiye
GET /api/news?q=Antalya&limit=10
GET /api/aircraft?callsign=TK1923
GET /api/earthquakes?min=2&limit=20
GET /api/wildfires?q=Manavgat
GET /api/wildfires/nearest?q=Antalya        ← nearest fire hotspot (lat/lon + FRP)
GET /api/cameras?q=Fethiye&discover=1
GET /api/live?q=Fethiye                     ← combined bundle
GET /api/snap/aircraft?callsign=TK1923
GET /api/snap/camera?q=Fethiye
GET /api/snap/wildfire?q=Antalya            ← fire snap PNG path + metadata
GET /api/narration?q=Fethiye&auto=1&duration=36
```

---

## Agent Autopilot

### Deep-link URL

```bash
open "http://127.0.0.1:5001/?q=Fethiye&preset=showcase&aspect=9-16&poi=skip&autostart=1"
```

| Param | Values |
|-------|--------|
| `q=` | place name |
| `lat=`, `lon=` | coordinate pair |
| `preset=` | `showcase` · `orbit` · `reveal` · `flyover` · `top-down` |
| `aspect=` | `16-9` · `9-16` · `1-1` · `4-5` · `21-9` · `4-3` · `3-4` |
| `poi=` | `skip` (36 s) · `auto` · `names:A,B` |
| `duration=` | seconds |
| `narrate=` | `auto` or literal text |
| `autostart=1` | record immediately, no modal |

### JS Bridge

```js
await window.celebiPlug.search("Fethiye", { autoTune: true });
window.celebiPlug.setPreset("orbit");
window.celebiPlug.setAspect("9-16");
const blob = await window.celebiPlug.record();
```

---

## Project Structure

```
.
├── app.py                  Flask: studio + /api/* endpoints
├── cli.py                  argparse CLI
├── celebi                  bash wrapper
├── legal_guard.py          source whitelist + record filters
├── providers/              one adapter per upstream data source
├── modules/                provider selection + fallback chains
├── utils/                  stdlib-only helpers (http, geocode, tts, film, staticmap…)
├── static/
│   ├── script.js           Mapbox, Pilot engine, MediaRecorder, autopilot
│   ├── narration.js        opt-in Web Audio mixer for TTS narration
│   └── style.css
├── templates/index.html    studio UI
├── install.md              first-run setup guide
├── SKILL.md                agent usage reference
└── AGENTS.md               code priorities for contributors
```

---

## Requirements

- Python 3.10+
- Flask 3.x (`pip install -r requirements.txt`)
- A GUI browser with WebGL/GPU and MP4/H.264 encoder support — required for recording
- A free Mapbox public token (`pk.`) for satellite imagery and static maps
- **Optional:** Pillow (`pip install Pillow`) for info-card overlays on PNG snaps
- **Optional:** `yt-dlp` on PATH for YouTube live camera discovery
- **Optional:** `WINDY_WEBCAMS_API_KEY` for Windy webcam discovery
- **Optional:** `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` for LLM-generated narration

---

## License

MIT
