---
name: celebi-plug
description: Day-to-day rules for working on CelebiPlug — running the Flask studio, walking users through the Mapbox public-token onboarding, loading GeoJSON, editing cinematic Mapbox 3D drone-style camera presets, and exporting 60-second MP4/WebM videos from the browser. For first-time install, read install.md instead.
---

# CelebiPlug Skill

CelebiPlug is a single-page Flask + JavaScript app that turns GeoJSON into 60-second cinematic 3D drone-style videos. It runs entirely in the browser on top of **Mapbox GL JS v3**, using a user-supplied Mapbox **public** token (`pk.…`) for satellite imagery, `mapbox-terrain-dem-v1` 3D terrain, and `composite/building` fill-extrusion 3D buildings.

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
   - Preview or record (`MediaRecorder` → MP4/H.264 on Chromium 134+ / Safari, WebM/VP9 fallback otherwise).

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

7. Record the final 60-second `.mp4` (or `.webm` on the fallback path), then report the downloaded filename/location along with the chosen preset, aspect ratio, subject, and any limitations encountered.

## Input modes

The left-rail Source block has four tabs that all flow into the same downstream pipeline (POI scan → presets → record):

- **File** — drop a `.geojson` or `.json`. Use this whenever the user supplies an actual file or a known boundary.
- **Search** — type a place name. Hits the Mapbox Geocoding API and pins the first result; uses the geocoder's `bbox` when it's a sensible size (< 0.4° span), otherwise drops a 150m square at the center. Best for "make a video of Sultanahmet."
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
   http://127.0.0.1:5001/?q=Sultanahmet&aspect=9-16&poi=auto&autostart=1#token=pk.XXX
   ```

3. **Welcome screen (manual)** — user opens `http://127.0.0.1:5001` once and pastes their `pk.` token. Use only when the agent has neither shell access nor URL control.

Once the token is reachable, drive the studio through one of three control surfaces.

### `/record` curl — VPS / headless agent (no local browser)

When the agent runs on a VPS or any environment without a graphical browser, run CelebiPlug in Docker (`docker compose up -d`) and call the bundled `/record` endpoint. The container drives a Chromium under Xvfb internally and streams the recorded file back (`.mp4` when H.264 is available, `.webm` fallback otherwise):

```bash
curl -OJ 'http://127.0.0.1:5001/record?q=Ayasofya+Camii&aspect=16-9&poi=auto&preset=showcase'
```

Query params mirror the deep-link URL below (`q`/`lat`/`lon`/`radius`/`preset`/`aspect`/`poi`); `autostart` is implicit. Use `curl -OJ` so the server-provided `.mp4` / `.webm` extension is preserved. The endpoint returns `503` when the Docker render backend isn't available, `400` when no Mapbox token is configured, and `500` with worker stderr on render failure. A 60s shot takes ~80–120s under software WebGL; 36s sparse mode (`poi=skip`) finishes ~50–70s.

Use this path only when the agent **cannot** open a GUI browser — on a Mac/PC dev box, the deep-link URL below is faster (real GPU).

### Deep-link URL params — useful when launching a fresh tab

```
http://127.0.0.1:5001/?q=Tuzla+Mahallesi+Fethiye&preset=showcase&aspect=16-9&poi=auto&autostart=1
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
- `autostart=1` — wait for tiles, then trigger record automatically; the file downloads through the browser (`.mp4` on Chromium 134+/Safari, `.webm` otherwise), no result modal.

Never put a Mapbox token in the **query string** (it would hit the server log). Only the `#token=` **hash fragment** form above is safe — browsers do not transmit hash fragments in HTTP requests.

**Agent conversation pattern** — fully chat-native. The agent asks at most four questions, then triggers. The user never has to open the studio UI.

**Operator UX contract** — the agent should feel transparent and talkative during execution:

- Start each run with a short ASCII banner and one-line intent summary.
- Between major steps (clone/install/start/check/record), post a short status line in plain language.
- Before first record attempt, report **where the token came from**: `MAPBOX_TOKEN` env, project `.env`, hash-bootstrap, or not found.
- Never print the raw token; only masked form is allowed (example: `pk.***ABCD`).
- If a token is already present from a previous run, say that explicitly so the user understands why no new token was asked.
- If `/root/celebi-plug` (or target dir) already exists, run `git pull --ff-only` before any install/record steps and report the active commit hash.

Suggested banner:

```text
  ____     _      _     _  ____  _ _
 / ___|___| | ___| |__ (_)/ ___|| (_)_ __
| |   / _ \ |/ _ \ '_ \| | |  _| | | '_ \
| |__|  __/ |  __/ |_) | | |_| | | | | | |
 \____\___|_|\___|_.__/|_|\____|_|_|_| |_|
```

Suggested preflight token-source check (`bash`, masked output only):

```bash
token_src="none"
token_val=""
if [ -n "${MAPBOX_TOKEN:-}" ] && printf '%s' "$MAPBOX_TOKEN" | grep -q '^pk\.'; then
  token_src="env:MAPBOX_TOKEN"
  token_val="$MAPBOX_TOKEN"
elif [ -f .env ]; then
  token_val="$(awk -F= '$1=="MAPBOX_TOKEN"{print $2}' .env | tr -d "\"'[:space:]")"
  if printf '%s' "$token_val" | grep -q '^pk\.'; then
    token_src=".env"
  else
    token_src="none"
    token_val=""
  fi
fi
masked="(none)"
if [ -n "$token_val" ]; then
  masked="$(printf '%s' "$token_val" | sed -E 's/^(pk\.).*(.{4})$/\1***\2/')"
fi
echo "token_source=$token_src token_masked=$masked"
```

**Hard safety rules for VPS `/record` runs** (must follow):

- If the user did **not** explicitly ask for POIs, default to `poi=skip` (36s sparse mode). Do not silently switch to `poi=auto`.
- Never report success from a failed HTTP call. Success requires HTTP `200`.
- Never copy error bodies (`/tmp/rec_body.txt` etc.) into `.mp4` filenames.
- Treat outputs under `2MB` as suspicious; verify with `ffprobe` before declaring success.
- Success gate: container format is video and duration is reasonable (`>=30s` for sparse runs).
- If validation fails, report failure clearly with HTTP code + first error lines + short docker log tail.

Suggested VPS validation block:

```bash
set -e
cd /root/celebi-plug
resp_code="$(curl -sS -L -OJ -w '%{http_code}' \
  'http://127.0.0.1:5001/record?q=Ayasofya+Camii&aspect=16-9&poi=skip&preset=showcase' \
  -o /tmp/record_body.bin)"
echo "http_code=$resp_code"
if [ "$resp_code" != "200" ]; then
  echo "record_failed_http=$resp_code"
  docker compose logs --tail=120 | sed -n '1,120p'
  exit 1
fi
latest="$(ls -t celebi-plug-* 2>/dev/null | head -1)"
test -n "$latest"
size="$(stat -c '%s' "$latest")"
echo "artifact=$latest size=$size"
if [ "$size" -lt 2000000 ]; then
  echo "record_failed_small_file"
  ffprobe -v error -show_entries format=format_name,duration -of default=nk=1:nw=1 "$latest" || true
  exit 1
fi
ffprobe -v error -show_entries format=format_name,duration -of default=nk=1:nw=1 "$latest"
```

0. **Token** (only on the very first job; skip on subsequent jobs) — "İlk kurulum için Mapbox public token'ına ihtiyacım var. `pk.` ile başlayan token'ını paylaş — `sk.` ile başlayan secret token'ı kullanma. Token bilgisayarında `.env` dosyasında kalacak, hiçbir sunucuya gitmeyecek." Validate it starts with `pk.`; if it starts with `sk.`, refuse and re-ask. Then persist:

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

Open with `open "$URL"`, wait ~38–72s depending on mode, then `ls -t ~/Downloads/celebi-plug-* | head -1` (extension is `.mp4` or `.webm` depending on the browser).

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
await window.celebiPlug.search("Sultanahmet, Istanbul");
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
- MIME type is probed MP4-first so modern Chromium / Safari record straight to `.mp4`: `video/mp4;codecs=avc1.42E01F,mp4a.40.2` → `avc1,mp4a` → `avc1` → `mp4` → `webm;vp9,opus` → `vp9` → `vp8` → `webm`. The download extension follows `blob.type` (`mp4` / `webm`).
- `videoBitsPerSecond: 12_000_000`.
- Output filename: `celebi-plug-<preset>-<iso-timestamp>.<mp4|webm>`.

Modern Chromium / Safari users already get `.mp4` natively — no conversion needed. Only the WebM fallback path (older browsers, Firefox) requires post-processing if MP4 is required downstream; the project deliberately ships no FFmpeg dependency, but the user can convert their own `.webm` locally:

```bash
ffmpeg -i celebi-plug-pilot-*.webm -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p output.mp4
```

Do **not** add a server-side conversion route or ship ffmpeg.wasm. That defeats the drop-in install promise.

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
- Keep the file tree minimal at root: `app.py`, `requirements.txt`, `templates/`, `static/`, plus the four agent-facing markdown files (`README.md`, `install.md`, `SKILL.md`, `AGENTS.md`).
- Don't reintroduce Cesium. CelebiPlug is a Mapbox project.
- Don't add server-side rendering, ffmpeg, or token-handling endpoints.
- Don't break the 60-second timing or 2-rotation count of the Pilot preset without a user request.
