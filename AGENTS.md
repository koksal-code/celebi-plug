CelebiPlug is a cinematic 3D drone-shot recorder built on Flask + Mapbox GL JS v3.
It is now a local-only app: record inside a local GUI browser.

# Code priorities
- Cinematic feel beats feature breadth
- Deterministic camera math; no `flyTo` / `easeTo` during recording
- Public Mapbox tokens only — never `sk.`
- Local-first install: browser + GPU/WebGL required
- Every input source (file, search, pin, box, autopilot URL, JS API) funnels through one `loadGeoJsonObject` pipeline

# Overview
- `app.py` — Flask studio route (`/`) and local-only guard on `/record`
- `templates/index.html` — welcome + studio, source tabs (file/search/pin/box), HUD, result modal, settings modal
- `static/script.js` — Mapbox + 4 input modes + geocoder + Overpass + Pilot scene engine (full 60s and sparse 36s) + MediaRecorder + autopilot URL handler + `window.celebiPlug` API
- `static/style.css` — geo-cinema design system

`SKILL.md` tells agents how to use the studio, drive deep-link/autopilot, and map free-form user commands onto preset/poi URL params.
`install.md` tells agents how to install the local browser flow and bootstrap token via `.env`.

# Contributing
Prefer the smallest diff that fixes the issue.
Do not reintroduce Docker/headless `/record` workflow unless explicitly requested.
