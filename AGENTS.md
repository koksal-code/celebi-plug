CelebiPlug is a cinematic 3D drone-shot recorder built on Flask + Mapbox GL JS v3. A place (GeoJSON file, geocoded query, map pin, or drag-box) in; a 36- or 60-second `.mp4` (H.264) or `.webm` (VP9 fallback) out — fully in the browser, no conversion step. Agent-drivable via deep-link URLs and a `window.celebiPlug` JS bridge.

# Code priorities
- Cinematic feel beats feature breadth
- Deterministic camera math; no `flyTo` / `easeTo` during recording
- Public Mapbox tokens only — never `sk.`
- Drop-in install: no FFmpeg, no backend rendering, no auth
- Every input source (file, search, pin, box, autopilot URL, JS API) funnels through one `loadGeoJsonObject` pipeline

# Overview
- `app.py` — Flask, two routes (`/` studio, `/record` Docker-only headless render); reads `MAPBOX_TOKEN` from env var or `.env` for chat-native token bootstrap
- `render_worker.py` — Playwright script invoked by `/record`; opens the autopilot URL under Xvfb and saves the MediaRecorder MP4 download
- `Dockerfile` + `docker-compose.yml` — VPS / headless deployment that bundles Chromium + Xvfb + Playwright
- `templates/index.html` — welcome + studio, source tabs (file/search/pin/box), HUD, result modal, settings modal
- `static/script.js` — Mapbox + 4 input modes + geocoder + Overpass + Pilot scene engine (full 60s and sparse 36s) + MediaRecorder + autopilot URL handler + `window.celebiPlug` API
- `static/style.css` — geo-cinema design system

`SKILL.md` tells agents how to use the studio, drive autopilot, choose between `/record` (VPS) vs deep-link URL (local browser), and map free-form user commands onto preset/poi URL params.
`install.md` tells agents how to install it, bootstrap the token chat-natively via `.env`, and trigger a one-shot recording from a terminal (or `docker compose up` on a VPS).

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug. Don't introduce server-side rendering, FFmpeg, or new dependencies without strong cause.
