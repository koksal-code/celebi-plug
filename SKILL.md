---
name: celebi-plug
description: Day-to-day rules for working on CelebiPlug — running the Flask studio, walking users through the Mapbox public-token onboarding, loading GeoJSON, editing cinematic Mapbox 3D drone-style camera presets, exporting 36s/60s MP4 videos from a GUI browser, and using the local geo-intelligence modules (weather, news, aircraft, earthquakes, wildfires, public cameras) via /api/* and the celebi CLI. For first-time install, read install.md instead.
---

# CelebiPlug Skill

CelebiPlug is a single-page Flask + JavaScript app that turns GeoJSON into cinematic 3D drone-style videos (60s full Pilot or 36s sparse no-POI mode). It runs entirely in the browser on top of **Mapbox GL JS v3**, using a user-supplied Mapbox **public** token (`pk.…`) for satellite imagery, `mapbox-terrain-dem-v1` 3D terrain, and `composite/building` fill-extrusion 3D buildings.

Alongside the recording studio, the same Flask process exposes six **geo-intelligence side modules** — weather, news, aircraft, earthquakes, wildfires, and public cameras — under `/api/*` and via a `./celebi` CLI. The defaults are free/open data (Open-Meteo, RSS, OpenSky, AFAD/Kandilli/USGS, NASA FIRMS, OpenStreetMap Nominatim, a curated public-camera registry); tokens are only needed to switch providers. None of these modules touch the recording pipeline.

For first-time install and Mapbox token bootstrap, read `install.md`. This file covers everything *after* the studio is up.

## Core workflow

When helping with CelebiPlug:

1. **Onboarding flow must stay intact:**
   - Welcome screen — staggered hero, language switcher top-right, token card.
   - Demand a Mapbox **public** token (`pk.…`). Refuse `sk.…`.
   - Save to `localStorage` under `celebi-plug_mapbox_token`. Never send the token to the server.
   - Open the studio only after the token validates.

2. **Studio flow must stay intact:**
   - Upload GeoJSON into the left rail.
   - Render the GeoJSON: 3D extrusion for polygons (red), red line for line/polygon outlines, red circle for points.
   - Scan nearby OSM POIs via Overpass (3 endpoints with failover).
   - Pick aspect ratio (7 options), preset (5 options).
   - Preview or record only after the local/WebGL/MP4 system check passes (`MediaRecorder` → MP4/H.264).

3. **Presets are pure functions of `t ∈ [0, 1]`.** Each returns `{ center: [lng, lat], zoom, pitch, bearing }`. The Pilot preset may additionally return `{ fade, polygonOpacity }`.

4. **All animation is `map.jumpTo` inside `requestAnimationFrame`.** Do **not** use `flyTo` / `easeTo` during recording — they fight the per-frame control needed for deterministic capture and produce frame skipping on slower GPUs.

## Drone operator mode

When the user asks for a cinematic video of a place, area, route, landmark, parcel, or GeoJSON, treat CelebiPlug as the available browser-native geo-cinema drone.

1. Determine the input type:
   - If the user provides a `.geojson` or `.json` file, use it directly.
   - If the user provides coordinates, a polygon, or a route, convert it into valid GeoJSON with coordinates in `[longitude, latitude]` order.
   - If the user only gives a place name, ask for a GeoJSON boundary or exact coordinates unless a reliable geocoding/source tool is available.

2. Choose the shot style:
   - `Pilot` for dramatic area coverage.
   - `Orbit` for landmarks and compact areas.
   - `Reveal` for cinematic introductions.
   - `Flyover` for routes, roads, coastlines, rivers, and paths.
   - `Top-down` for parcels, planning, inspection, and map-like views.

3. Choose aspect ratio:
   - `16:9` for YouTube, websites, and presentations.
   - `9:16` for Reels, TikTok, and Shorts.
   - `1:1` or `4:5` for social feed posts.

4. Open the local studio at `http://127.0.0.1:5001`, ensure a `pk.` Mapbox public token is available, and never request or use an `sk.` secret token.

5. Upload the GeoJSON, wait for satellite imagery, 3D terrain, 3D buildings, and nearby POIs to load, then select up to two POIs only if they improve the shot.

6. Preview before recording. If framing is poor, adjust preset, aspect ratio, or POIs and preview again.

7. Record the final take (`60s` full, or `36s` sparse if POI skip path is selected), then report the downloaded filename/location along with the chosen preset, aspect ratio, subject, and any limitations encountered.

## Input modes

The left-rail Source block has four tabs that all flow into the same downstream pipeline (POI scan → presets → record):

- **File** — drop a `.geojson` or `.json`. Use this whenever the user supplies an actual file or a known boundary.
- **Search** — type the user's requested place name. Hits the Mapbox Geocoding API and pins the first result; uses the geocoder's `bbox` when it's a sensible size (< 0.4° span), otherwise drops a 150m square at the center.
- **Pin** — click on the map (auto-armed when this tab is active) or paste `lat, lon[, radius_m]`. A square polygon of `R` meters (default 80, settable in the input) is synthesized.
- **Box** — drag a rectangle on the map; the bbox becomes the polygon. Only reachable via the UI tab or the `loadBbox` / `armBboxDraw` JS bridge methods — no URL param.

Prefer the simplest tab that matches the input. The agent should not switch tabs mid-recording.

## Agent autopilot

The studio exposes two non-UI control surfaces so a browser-automation agent can drive a shot end-to-end without clicking. The Mapbox token must be reachable by the page. Three ways to put it there, in priority order:

1. **`.env` file (chat-native install — recommended for agents with shell access)** — the agent collects the `pk.` token in chat and writes it to the project's `.env`:

   ```bash
   echo 'MAPBOX_TOKEN=pk.eyJ1...' > /path/to/celebi-plug/.env
   ```

   On the next page load, `app.py` reads `MAPBOX_TOKEN` from `.env`, injects it into the rendered HTML as `window.__CELEBI_ENV_TOKEN__`, and `script.js` seeds it into `localStorage`. The welcome screen is **skipped on the very first open** — full chat-native install, the user never sees the studio UI. `.env` is `.gitignored`; the token never leaves the user's machine. Only `pk.` tokens are accepted (anything else is silently ignored).

2. **URL hash fragment** — `http://127.0.0.1:5001/#token=pk.XXX`. The page reads `#token=…`, writes to `localStorage`, then strips it from the URL via `history.replaceState`. Hash fragments are **never sent to the server** (no Flask log, no proxy). Useful when the agent does not have filesystem access. Can be combined with autopilot params:

   ```
   http://127.0.0.1:5001/?q=<URL_ENCODED_PLACE>&aspect=9-16&poi=auto&autostart=1#token=pk.XXX
   ```

3. **Welcome screen (manual)** — user opens `http://127.0.0.1:5001` once and pastes their `pk.` token. Use only when the agent has neither shell access nor URL control.

Once the token is reachable, drive the studio through one of three control surfaces.

### GUI runtime

CelebiPlug records only when the runtime has a GUI browser, GPU/WebGL, and MP4/H.264 support.

- If GUI/GPU/MP4 checks fail, say exactly: `GPU/GUI yok, Çelebi uçuş yapamaz. Kurulumu iptal ediyorum; kurulumdan kalan dosyaları sileyim mi?`
- Use `python3 app.py` + `http://127.0.0.1:5001`.
- Record through the studio, autopilot URL, or `window.celebiPlug.record()`.

### Deep-link URL params — useful when launching a fresh tab

```
http://127.0.0.1:5001/?q=<URL_ENCODED_PLACE>&preset=showcase&aspect=16-9&poi=skip&autostart=1
```

Source (choose one):
- `q=` — place name; page geocodes locally via the saved Mapbox token. If `radius` is omitted, the page **auto-tunes** from the geocoder's `place_type` (address → 30m, neighborhood → 100m, place → 600m, etc.). The more specific the address (street + door number), the tighter the framing.
- `lat=`, `lon=` — coordinate pair; uses `radius` (default 60m).

Shot controls:
- `preset` — `showcase` | `orbit` | `reveal` | `flyover` | `top-down`.
- `aspect` — `16-9` | `9-16` | `1-1` | `4-5` | `21-9` | `4-3` | `3-4`.
- `radius=` — optional meters; overrides auto-tune.

POI behaviour (`poi=`):
- omitted — no POIs are auto-selected (cinematic uses synthetic offsets for showcase scenes 3 & 4).
- `auto` or `auto:N` — auto-select the closest N POIs (max 2).
- `skip` — explicitly skip POIs.
- `names:A,B` — select POIs whose name matches A or B (substring, case-insensitive).

Trigger:
- `autostart=1` — wait for tiles, then trigger record automatically; the `.mp4` downloads through the local GUI browser, no result modal.

Never put a Mapbox token in the **query string** (it would hit the server log). Only the `#token=` **hash fragment** form above is safe — browsers do not transmit hash fragments in HTTP requests.

**Agent conversation pattern** — fully chat-native. During first setup, finish installation first and stop there. Only start a recording after the user explicitly asks for a video.

**First-time install flow**:

1. Clone the repo, or if it already exists, update it with `git pull --ff-only` and report the active commit hash.
2. Read `README.md`, `install.md`, `AGENTS.md`, and `SKILL.md`.
3. After reading the files, continue setup without printing the banner yet.
4. Ask for the Mapbox public token directly: "Kurulumu tamamlamak için Mapbox public tokenını paylaşabilir misin? Token `pk.` ile başlamalı; tam halini ekranda tekrar yazmayacağım."
5. Validate that the token starts with `pk.`. If it starts with `sk.`, ask for a public token instead.
6. Write the token to the project `.env` as `MAPBOX_TOKEN=...`, then say only `token hazır`.
7. Check local runtime prerequisites before starting:
   - GUI browser available (`chrome/chromium/firefox/safari` family)
   - WebGL/GPU-capable local machine
   - MP4/H.264 MediaRecorder support
8. If prerequisites are available, start local flow and run a simple health check (`GET /`).
9. If prerequisites are not available, stop setup and say exactly: `GPU/GUI yok, Çelebi uçuş yapamaz. Kurulumu iptal ediyorum; kurulumdan kalan dosyaları sileyim mi?`
10. Delete install leftovers only after the user confirms cleanup. Do not delete without confirmation.
11. In the final setup-complete message, print the exact plain ASCII banner below at the very top, then explain the local URL and basic usage in one short summary.

**Operator UX contract** — the agent should feel transparent and talkative during execution:

- On first setup, show the exact ASCII banner below only when setup is complete, at the very top of the final setup summary.
- Between major steps (clone/docs/token/install/start/check/record), post a short status line in plain language.
- During first setup, explicitly say runtime decision (`GUI browser ready` or `GPU/GUI yok, Çelebi uçuş yapamaz. Kurulumu iptal ediyorum; kurulumdan kalan dosyaları sileyim mi?`).
- Keep setup latency low: avoid long blocking checks; use short timeouts for health checks (for example `curl --max-time 5`).
- Keep token talk minimal. In first install, ask for token once and continue.
- Keep token output minimal and safe: report `token hazır`.
- If a valid token is already present from a previous run, simply say `token hazır` and continue.
- Terminal command hygiene:
  - Write shell commands in plain ASCII only.
  - Put Turkish status text in chat messages, not inside shell command strings.
  - Prefer one command per step; avoid long chained commands with `&&` for routine checks.

Exact banner:

```text
+------------------------------------------------------------+
|                         CELEBI-PLUG                        |
|                     GEO-CINEMA STUDIO                      |
|                 MAPBOX 3D DRONE RECORDER                   |
+------------------------------------------------------------+
```

**Local recording notes**:

- First-time install is token-first. Ask for token before recording.
- Ask target, aspect, and POI preference.
- If user did not explicitly ask for POIs, default to `poi=skip` (36s sparse mode).
- For agent-run recordings, keep the browser foregrounded. If launching Chrome yourself, use a temporary profile with background throttling disabled:

  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9224 \
    --user-data-dir=/tmp/celebi-plug-chrome-profile \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --autoplay-policy=no-user-gesture-required \
    "http://127.0.0.1:5001"
  ```

- Run one primary recording and, if needed, one retry with the same params.
- Verify the MP4 duration before reporting success. A `poi=skip` take should be about 36s; a full take should be about 60s. If the file is much shorter, discard it and retry with the browser visible/throttling disabled.
- Report file path, size, format, and duration clearly.

0. **Token** (during first setup, before recording) — "Kurulumu tamamlamak için Mapbox public tokenını paylaşabilir misin? Token `pk.` ile başlamalı; tam halini ekranda tekrar yazmayacağım." Validate it starts with `pk.`; if it starts with `sk.`, briefly explain and ask for a public token. Then persist:

   - **If the agent has shell access to the celebi-plug directory** (recommended): `echo 'MAPBOX_TOKEN=pk.XXX' > /path/to/celebi-plug/.env`. This is a one-time write — every subsequent shot reuses the same `.env` automatically. No URL hash needed.
   - **If the agent only has URL control:** append `#token=pk.XXX` to the autopilot URL on the first run; on later runs, the token is already in `localStorage` and the hash is omitted.

1. **Aspect** — "Hangi en-boy oranı?  16:9 (YouTube/web) · 9:16 (Reels/TikTok) · 1:1 (feed) · 4:5 (feed) · 21:9 (cinemascope) · 4:3 · 3:4. Varsayılan 16:9."
2. **POIs** — geocode the place via Nominatim or Mapbox, then call Overpass for nearby named POIs (see snippet below). Present the list to the user:
   "Yakında şu yerleri buldum:  1) X kafe (35m) · 2) Y camii (110m) · 3) Z park (220m) · 4) ... Hangilerini çekime dahil edeyim? (numara/isim, veya 'hiçbiri', veya 'en yakın 2')"
3. **Speed mode** — only if user said no POIs: "Sade 36s çekim mi, yoksa tam 60s kullanılsın mı?" (varsayılan: sade = `poi=skip`).

Construct the URL:

```
http://127.0.0.1:5001/?
  q=<place>
 &preset=<see vocabulary below>
 &aspect=<choice>
 &poi=<auto|skip|names:A,B>
 &autostart=1
 [#token=pk.XXX]   ← only on the first run per browser
```

Open the URL in the foreground recording browser, wait ~38–72s depending on mode, then `ls -t ~/Downloads/celebi-plug-*.mp4 | head -1`. Verify duration before reporting success.

If user asks for a **download link**, do not assume a public HTTP server already exists. First state one of:
- direct transfer command (`scp`/`rsync`) as the default safe path, or
- temporary HTTP link only after explicitly noting port exposure and runtime scope.

**Overpass POI snippet** (the agent runs this in bash, same query the page uses):

```bash
curl -sG https://overpass-api.de/api/interpreter --data-urlencode \
'data=[out:json][timeout:20];
(
  nwr["name"]["shop"](around:600,LAT,LON);
  nwr["name"]["amenity"~"cafe|restaurant|mosque|hospital|bank|atm|fuel|cinema|theatre|library|university"](around:600,LAT,LON);
  nwr["name"]["tourism"~"hotel|museum|attraction|viewpoint"](around:600,LAT,LON);
  nwr["name"]["leisure"~"park|stadium"](around:600,LAT,LON);
);
out tags center 30;'
```

If geocoding fails (Turkish street-level addresses are spotty in Mapbox), broaden and retry: street → neighborhood → district → city.

**Command vocabulary** — the studio UI only shows Pilot, but every preset stays valid via `preset=`. Map free-form user phrasings onto presets:

| User says | `preset=` | Why |
|---|---|---|
| "etrafında dön", "döner çekim", "orbit"          | `orbit`    | single 360° rotation, breathing pitch |
| "yakından aç", "uzaktan başla yaklaş", "reveal"  | `reveal`   | 3-beat far → close arc |
| "yolu/sokağı/rotayı takip et", "boyunca uç"      | `flyover`  | follow polyline with anticipation bearing |
| "kuşbakışı", "üstten göster", "harita gibi"      | `top-down` | overhead descent, half rotation |
| Anything else / default                          | `showcase` | the full 5-scene Pilot |

The agent does not have to expose preset names to the user — it picks the right one based on intent and bakes it into the URL.

### `window.celebiPlug` JS bridge — for in-page agent control

```js
// pick a target — four options, mirroring the UI tabs
await window.celebiPlug.loadCoordinates([28.9784, 41.0082], 80);
await window.celebiPlug.search("USER_REQUESTED_PLACE");
await window.celebiPlug.loadGeoJson(geojsonObject, "label");
await window.celebiPlug.loadBbox([west, south, east, north]);

// configure shot + record
window.celebiPlug.setPreset("orbit");
window.celebiPlug.setAspect("9-16");
const blob = await window.celebiPlug.record();                      // downloads + returns Blob
const silent = await window.celebiPlug.record({ download: false }); // Blob only
```

Other methods: `isReady()`, `hasMap()`, `getState()`, `preview()`, `stopPreview()`, `selectSourceTab("upload"|"search"|"pin"|"box")`, `armPinPick()`, `disarmPinPick()`, `armBboxDraw()`, `disarmBboxDraw()`, `getPois()`, `selectPois([0,1])`, `autoPickPois(n)`, `pickPoisByNames(["camii"])`, `clearPois()`, `setSkipPoiScenes(true)`.

When the user gives only coordinates, prefer `loadCoordinates`. When the user gives a place name, prefer `search` (it leverages Mapbox geocoder bbox for better framing). Falling back to the file-upload UI is still valid when the user provides an actual `.geojson` file.

## Mapbox token guidance

- Public tokens only (`pk.…`). Browser-safe, browser-stored.
- Never write a server-side token-handling endpoint. Tokens stay in `localStorage`.
- If a user pastes `sk.…`, refuse and explain why.

## GeoJSON handling

Supported geometry types:

- `FeatureCollection`, `Feature`
- `Point`, `MultiPoint`
- `LineString`, `MultiLineString`
- `Polygon`, `MultiPolygon`
- `GeometryCollection`

Camera-route extraction order:

1. First `LineString` in the file.
2. Flattened `MultiLineString`.
3. Outer ring of the first `Polygon`.
4. Outer ring of the first inner polygon in `MultiPolygon`.
5. Bounding-box rectangle if only Points exist.

Parcel zoom is computed from polygon area in m² (Shoelace on the first ring) and mapped via `getZoomFromArea` to a Mapbox zoom in `[15, 19]`. `farZoom = parcelZoom − 3`.

## Cinematic presets

All presets live in `static/script.js` and dispatch via `getCinematicScene(t)`.

- **`showcase` (display name: Pilot)** — 60s, 5 equal-weight scenes, 2 full rotations (`720°` total bearing), fade-to-black transitions between scenes (`fadeDuration: 0.02`), polygon opacity varies per scene (`[0.45, 0.70, 0.15, 0.15, 0.60]`). Scene 1: far center. Scene 2: close center, 75° pitch. Scenes 3–4: selected POIs when available, otherwise synthetic offset targets near the GeoJSON center. Scene 5: return to center. **Ported verbatim from the v2 source's `getSceneState`. Do not rebalance the timings unless the user explicitly asks.**

- **`orbit`** — single 360° elegant rotation with breathing pitch (50° → 78° → 50°) and slow zoom-in.

- **`reveal`** — 3-beat keyframe arc: far → mid → close, pitch ramps from 18° to 74°.

- **`flyover`** — follow `routeCoordinates` segment-by-segment with bearing aligned to travel direction; uses anticipation lookahead (`headingFromTo`).

- **`top-down`** — slow descent from 2° to 30° pitch with half a rotation.

When the user changes preset, call `resetVisualState()` so polygon opacity and the fade overlay snap back to defaults (the next preset may not touch them).

## Video settings

Supported aspect ratios:

- `16:9`, `9:16`, `1:1`, `4:5`, `21:9`, `4:3`, `3:4`

Aspect ratio is applied to the `.viewfinder` wrapper. Mapbox `map.resize()` is called ~100ms later. **Never** resize during recording — that invalidates `MediaRecorder`'s stream.

## Recording pipeline

The browser-only pipeline:

- Mapbox is created with `preserveDrawingBuffer: true` (required for `drawImage` from the WebGL canvas).
- A 2D `recordCanvas` mirrors the Mapbox canvas each frame and composites the fade overlay on top.
- The MediaRecorder stream is `recordCanvas.captureStream(30)`, not the Mapbox canvas directly. This is what makes fade-to-black transitions visible in the recorded output.
- Local/browser flow probes MP4/H.264 only: `video/mp4;codecs=avc1.42E01F,mp4a.40.2` → `avc1,mp4a` → `avc1` → `mp4`. If none are supported, recording stays disabled.
- `videoBitsPerSecond: 12_000_000`.
- Output filename in local/browser flow: `celebi-plug-<preset>-<iso-timestamp>.mp4`.

## i18n

Three languages, language switcher in the top bar of the welcome screen: `tr`, `de`, `en`. Strings live in the `translations` object in `static/script.js`. Use `data-i18n="key"` for text content and `data-i18n-html="key"` when the translated string contains HTML. Selection persists in `localStorage` under `celebi-plug_lang`.

When adding a new string, add it to all three dictionaries.

## Validation

After code changes:

```bash
python3 -m py_compile app.py
# JS — bracket/paren balance check via the project's Python validator,
# or simply curl the page and verify it loads:
curl -I http://127.0.0.1:5001
```

If the Flask server is running, the verification block in `install.md` covers UI smoke-testing.

## Style rules

- Keep the UI professional and publishable. Avoid toy/demo wording.
- Use "skill" or "agent skill" for agent integration.
- Keep the file tree minimal at root: `app.py`, `cli.py`, `celebi` wrapper, `legal_guard.py`, `providers/`, `modules/`, `utils/`, `requirements.txt`, `templates/`, `static/`, plus the four agent-facing markdown files (`README.md`, `install.md`, `SKILL.md`, `AGENTS.md`).
- Don't reintroduce Cesium. CelebiPlug is a Mapbox project.
- Don't add server-side rendering or token-handling endpoints.
- Don't break the full-Pilot timing (60s) or 2-rotation count without a user request.
- The recording pipeline (`templates/index.html`, `static/script.js`, `static/style.css`) is the cinematic core. Geo-intel modules must stay as side modules — never wire them into recording, never add a new heavy dependency (DB, auth, websockets, queues, pip packages beyond Flask).

## Geo-intelligence modules

The Flask process serves six read-only endpoints under `/api/*`, mirrored by the `./celebi` CLI. All defaults are free public sources; tokens only switch providers.

### Endpoints

```
GET /health
GET /api/weather?q=<place>                 # or ?lat=&lon= [&marine=1]
GET /api/news?q=<query>&limit=15
GET /api/aircraft?callsign=<code>          # or ?q=&radius_km=  or ?lat=&lon=&radius_km=
GET /api/earthquakes?min=<mag>&limit=
GET /api/wildfires?q=<place>               # or ?bbox=west,south,east,north
GET /api/cameras?q=<place>&radius_km=      # or ?lat=&lon=
```

Errors come back as `{"error": "..."}` with the matching HTTP status. The Flask process is loopback-only (`is_local_request`), so these endpoints are never exposed to the network.

### CLI

```bash
./celebi weather "Fethiye"
./celebi weather --lat 36.65 --lon 29.12 --marine
./celebi news "Antalya" --limit 10
./celebi aircraft TK1923
./celebi aircraft --place "Fethiye" --radius-km 80
./celebi earthquake --min 3
./celebi wildfire --place "Manavgat"
./celebi cameras "Fethiye"
```

The wrapper prefers `VIRTUAL_ENV/bin/python`, then `.venv/bin/python`, then system `python3`. Output is JSON on stdout.

### Provider chain & env switches

| Module | Default | Alt | Switch |
|---|---|---|---|
| Weather | `OpenMeteoProvider` | `OpenWeatherProvider` | `CELEBI_WEATHER_PROVIDER=openweather` + `OPENWEATHER_API_KEY` |
| News | `RSSProvider` (TR + global RSS) | `NewsAPIProvider` | `CELEBI_NEWS_PROVIDER=newsapi` + `NEWSAPI_KEY` |
| Aircraft | `OpenSkyProvider` | `AdsbLolProvider` | `CELEBI_AIRCRAFT_PROVIDER=adsb-lol`; optional `OPENSKY_USERNAME` / `OPENSKY_PASSWORD` |
| Earthquakes | `AfadProvider` → `KandilliProvider` → `UsgsProvider` | — | `CELEBI_EARTHQUAKE_PROVIDERS=afad,kandilli,usgs` (chain order) |
| Wildfires | `NasaFirmsProvider` (24h CSV) | — | optional `FIRMS_MAP_KEY` |
| Cameras | `OfficialCamerasProvider` (curated registry) | — | extend `providers/cameras.py` and whitelist in `legal_guard.py` |

Geocoder default is OpenStreetMap Nominatim; set `CELEBI_GEOCODER=mapbox` (and have a `pk.` token available) to route through Mapbox geocoding instead.

### Legal guard contract

Every provider declares its `(category, source_id)` at construction time. `legal_guard.ensure_source(...)` raises `LegalGuardError` if the source is not whitelisted. Every emitted record passes through `legal_guard.filter_record(...)`, which drops:

- Aircraft with military callsign prefixes (`RCH`, `PAT`, `SAM`, `GAF`, `TURAF`, `NATO`, …) and PIA/LADD/blocked flags.
- Camera entries whose name or operator matches `mobese`, `kgys`, `surveillance`, `private-cctv`, `police-cam`, or `law-enforcement`.

When the user asks for "kameralar" / "trafik kameraları" / "city cam", check `providers/cameras.py` first. If the desired feed is not there, do **not** scrape it — explain that CelebiPlug only surfaces curated public/official cameras and offer to add an entry that meets the whitelist criteria.

When the user asks for an aircraft by callsign that matches a military prefix, refuse and explain the policy in one short line.

### Agent usage pattern

If the user has already finished install, mix the modules into your replies as supporting context:

- "Fethiye'de hava nasıl?" → `./celebi weather "Fethiye"` (or `curl /api/weather?q=Fethiye`) → quote temperature / wind / sea suitability if `--marine` was requested.
- "Bugün son depremler?" → `./celebi earthquake --min 2 --limit 5`.
- "Manavgat'ta yangın var mı?" → `./celebi wildfire --place "Manavgat"`.
- "Antalya yakınında kamera?" → `./celebi cameras "Antalya" --radius-km 100`.

These are read-only commands and safe to run inline. Don't use them as a replacement for the recording flow — when the user asks for a *video*, fall back to the studio autopilot in the section above.

### Chat-flow integration

The geo-intel modules are designed to be used **during conversation**, not as standalone tools. The CLI works without the Flask server running — `cli.py` imports the modules directly — so the agent can pull live data even before `python3 app.py` is started.

**Choose the surface based on context:**

- **`./celebi <cmd>` (preferred for chat)** — no server needed, works from any terminal where the agent has shell access. Output is JSON; the agent reads it and replies in natural language.
- **`curl 127.0.0.1:5001/api/<cmd>` (when Flask is already running)** — same data, useful if the user has the studio open and you want to avoid a fresh interpreter boot.

**Intent → command mapping (Turkish + English):**

| User phrasing | Run | Reply pattern |
|---|---|---|
| "hava nasıl", "bugün sıcaklık", "rüzgar", "yağış" | `./celebi weather "<place>"` | One sentence: temp / wind / precipitation. Mention `observed_at` only if older than 1h. |
| "denize girilir mi", "dalga durumu", "marine" | `./celebi weather "<place>" --marine` | Quote `wave_height_m` + `sea_suitable`. |
| "haberler", "ne oluyor", "<şehir> haberleri" | `./celebi news "<place>"` | List 3–5 headlines with source + relative date. Skip duplicates. |
| "uçak nerede", "<callsign> nerede", "TKxxxx" | `./celebi aircraft <callsign> --map` | Quote callsign, lat/lon, alt, speed + paste `map.url` (Mapbox satellite still). If military prefix → refuse politely. |
| "uçağın fotoğrafını / haritasını at" | `./celebi aircraft <callsign> --snapshot` | Returns `snapshot_path` — surface the file path; the agent can attach it as an image. |
| "üzerimde uçak var mı", "yakın uçaklar" | `./celebi aircraft --place "<place>" --radius-km 80 --map` | Top 3 by altitude/distance, with origin country + per-aircraft map URL. |
| "deprem oldu mu", "son depremler", "Türkiye deprem" | `./celebi earthquake --min 2 --limit 5` | Magnitude + location + relative time. Mention source (AFAD/Kandilli/USGS). |
| "yangın var mı", "FIRMS", "wildfire" | `./celebi wildfire --place "<place>"` | Count + closest fire distance. If 0, say so plainly. |
| "kamera", "canlı yayın", "live cam" | `./celebi cameras "<place>" --radius-km 100` | List name + operator + URL. Refuse if the user asks for MOBESE/KGYS — explain whitelist policy in one line. |
| "şu kameranın görüntüsünü gönder", "tek karelik foto" | `./celebi cameras "<place>" --snapshot` | Returns `snapshot_path` per camera (satellite still of the camera's location when the source has no JPEG endpoint). |
| "bana <yeri> canlı göster" | `./celebi live "<place>" --snapshot` | One-paragraph summary: weather, fire/quake counts, kameralar (with URL), `snapshot_path` (Mapbox satellite still) — single chat-ready bundle. |
| "haritada göster", "uydudan göster" | `./celebi map "<place>" --snapshot` | Returns `map.url` (Mapbox satellite still) + saved PNG path. |

**Combining geo-intel with the recording studio** — the most powerful pattern is using the modules as pre-flight context for a cinematic take:

1. User: "Fethiye'nin cinematic videosunu çek."
2. Agent: runs `./celebi weather "Fethiye" --marine` and `./celebi wildfire --place "Fethiye"` quickly.
3. Agent: replies in one short paragraph — "Fethiye'de hava açık, 24°C, dalgalar 0.6m. Yakında aktif yangın yok. Cinematic çekime başlıyorum." — then launches the studio autopilot URL.
4. The recording flow itself is unchanged (see `Agent autopilot` above).

This gives the user a brief operator-style situational report before the 36s/60s shot rolls.

**Reply hygiene:**

- Summarize. Never paste the full JSON into chat unless the user explicitly asks for raw output.
- Round numbers (24.8 → "25°C"; 10.4 km/h → "10 km/h").
- Cite the data source in one short clause ("AFAD verisine göre…", "Open-Meteo'dan…", "OpenSky'da göründüğü kadarıyla…").
- If a module fails (network, rate limit, no data), say so briefly and fall back to the next provider — don't show stack traces.

**Refusal triggers (legal_guard reinforcement):**

- User asks for MOBESE / KGYS / private CCTV / police cameras → "CelebiPlug yalnızca resmi/halka açık kameraları gösterir; MOBESE veya benzeri gözetim sistemlerini sorgulamıyorum."
- User asks for a military callsign that hits the prefix filter → "Bu çağrı işareti askeri kategoride, gizliliği kapalı uçuşlar listelenmiyor."
- These are *guardrails*, not errors — the rest of the conversation continues normally.

**Artifact delivery — files, not links:**

The agent's job in the chat is to ATTACH the artifact, not paste a URL. Three commands return a path on disk; treat that path as the deliverable.

| User asks | Command | Deliverable |
|---|---|---|
| "şu uçağın haritasını gönder" / "TKxxxx nerede, foto" | `./celebi snap-aircraft <callsign>` | `card_path` (composite PNG when Pillow installed) **or** `snapshot_path` + `json_path` sidecar |
| "Fethiye'de canlı kameraya bak, görüntüsünü gönder" | `./celebi snap-camera "<place>"` | `snapshot_path` PNG — real live frame when the registry has a JPEG URL, satellite still otherwise. `card_path` if Pillow is installed. |
| "bana Fethiye'nin videosunu çek ve gönder" | `./celebi film "<place>" --aspect 9-16 --narrate auto` | `mp4_path` — full 36/60s cinematic MP4 (with TTS audio if `--narrate` is set). |

After running the command, parse the JSON result and **attach the file at `card_path`/`snapshot_path`/`mp4_path` to the chat reply.** Do not paste the path as text; the goal is the user sees the image/video inline.

If Pillow isn't installed, snap commands still deliver `snapshot_path` (raw PNG) — fall back to attaching that one plus a one-line caption derived from the JSON sidecar.

**Narration (browser-native, no ffmpeg):**

`celebi film --narrate auto` builds a 10-second narration script from the live geo-intel bundle (e.g. *"Çelebi Fethiye üstünde. Sıcaklık 24 derece. Rüzgâr 9 km/h. Yakında 9 aktif termal nokta var. Canlı kamera: Ölüdeniz Belcekız Plajı. Cinematic uçuş başlıyor."*), TTS-synthesises it locally (macOS `say` → AAC; Linux `espeak-ng` → WAV), and the studio mixes it into the recording via Web Audio → MediaRecorder. The .mp4 ships with H.264 + AAC, single file, no merge step.

Override the script with explicit text: `--narrate "Lütfen Ölüdeniz'in cinematic uçuşunu izleyin"`. Without a local TTS engine the recording is silent (the rest of the pipeline still works).

**Images and single-frame snapshots:**

Every place/aircraft/camera response can carry a static-map "frame" that the agent shares with the user. There are three transport options, pick the one that matches the chat surface:

1. **URL only** (cheapest) — pass `--map` (aircraft) / `--preview` (cameras) / use the `live` or `map` subcommand. The reply includes `map.url` pointing to Mapbox Static Images (satellite-streets style, orange pin). The chat client renders the URL inline if it supports image previews.
2. **Downloaded PNG path** — pass `--snapshot`. The CLI writes a one-frame PNG to `/tmp/celebi-snapshot-*.png` and returns the path. Use this when the agent has a file-attachment surface.
3. **Proxy stream** (when the Flask server is up) — `GET /api/snapshot.png?q=<place>` returns the bytes directly. Useful when the agent can hand the user an internal URL but not a Mapbox token-bearing one.

If `MAPBOX_TOKEN` is missing, the `map.url` is an OSM web page link instead of a still image (`is_image: false`). In that case the agent should say "haritada konumu bu link gösteriyor" and paste the URL rather than promising a single frame.

The `live` subcommand is the canonical "bana <yeri> canlı göster" handler. Its payload is purpose-built for one short paragraph:

```
Fethiye şu an 25°C, 10 km/h batı rüzgârı, dalga 0.6m — denize uygun.
Son 24 saat: aktif yangın 0, çevrede deprem 0.
Canlı kamera (Fethiye Belediyesi): https://www.fethiye.bel.tr/canli-yayin
Uydu görüntüsü (tek kare): /tmp/celebi-snapshot-abc.png
```

When the user asks "uçak nerede" with a callsign, use `--map`; when they explicitly ask for a *photo*, also add `--snapshot` and surface the path.
