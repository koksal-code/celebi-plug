CelebiPlug is a cinematic 3D drone-shot recorder built on Flask + Mapbox GL JS v3, plus a small local geo-intelligence API and CLI.
Recording requires a GUI browser with GPU/WebGL and MP4 support. The geo-intel modules only need a Python interpreter.

# Code priorities
- Cinematic feel beats feature breadth
- Deterministic camera math; no `flyTo` / `easeTo` during recording
- Public Mapbox tokens only — never `sk.`
- Runtime: GUI browser + GPU/WebGL + MP4 required for recording
- Every input source funnels through `loadGeoJsonObject`
- Geo-intel modules stay as side modules — they must not pull dependencies into the recording pipeline or add new pip packages (only stdlib + Flask)
- Every external data source is whitelisted in `legal_guard.py`; aircraft military prefixes and surveillance cameras (MOBESE/KGYS/etc.) are filtered out at this layer

# Overview
- `app.py` — Flask studio route + `/health` + `/api/{weather,news,aircraft,earthquakes,wildfires,cameras}`; no server-side recording
- `cli.py` + `celebi` — minimal argparse CLI that dispatches into `modules/`
- `legal_guard.py` — source whitelist, forbidden tokens, military / blocked-aircraft filter
- `providers/` — one adapter per upstream (Open-Meteo, OpenWeather, RSS, NewsAPI, OpenSky, ADS-B.lol, AFAD, Kandilli, USGS, NASA FIRMS, public cameras registry)
- `modules/` — provider selection by env var with free-default fallback; plus `snap` (single-frame artifact assembly), `narration` (text builder from live bundle), `live` (combined bundle)
- `utils/` — urllib wrapper + Nominatim/Mapbox geocoder (stdlib), `staticmap` (Mapbox Static Images URL builder), `snapshot` (URL → tmp file), `composite` (Pillow info-card, optional dep), `film` (headed Chrome launcher + Downloads watcher), `tts` (macOS `say` + `afconvert` / Linux `espeak-ng`)
- `static/narration.js` — opt-in Web Audio mixer that pipes `/api/narration` audio into MediaRecorder's stream when `?narrate=` URL param is set
- `templates/index.html` — welcome, studio, HUD, settings, result modal
- `static/script.js` — Mapbox, input modes, Pilot engine, MediaRecorder, autopilot/API
- `static/style.css` — geo-cinema design system

See `SKILL.md` for studio/autopilot usage and the geo-intel module reference, and `install.md` for local setup.

# Contributing
Prefer the smallest diff that fixes the issue.
Do not reintroduce Docker/headless recording unless explicitly requested.
Do not add a new *required* pip dependency. Optional ones (currently: Pillow for snap composite cards) are fine when their absence has a graceful fallback.
No database, auth system, websocket layer, or queue — the platform is intentionally stdlib-only on top of Flask.
When adding a new data source, whitelist it in `legal_guard.py` first, then add a provider class in `providers/<module>.py` and wire the selection in `modules/<module>.py`.
Narration is opt-in via `?narrate=` URL param; the existing silent-recording path must keep working byte-for-byte when the param is absent.
