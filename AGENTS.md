CelebiPlug is a cinematic 3D drone-shot recorder built on Flask + Mapbox GL JS v3.
Recording requires a GUI browser with GPU/WebGL and MP4 support.

# Code priorities
- Cinematic feel beats feature breadth
- Deterministic camera math; no `flyTo` / `easeTo` during recording
- Public Mapbox tokens only — never `sk.`
- Runtime: GUI browser + GPU/WebGL + MP4 required
- Every input source funnels through `loadGeoJsonObject`

# Overview
- `app.py` — Flask studio route; no server-side recording
- `templates/index.html` — welcome, studio, HUD, settings, result modal
- `static/script.js` — Mapbox, input modes, Pilot engine, MediaRecorder, autopilot/API
- `static/style.css` — geo-cinema design system

See `SKILL.md` for studio/autopilot usage and `install.md` for local setup.

# Contributing
Prefer the smallest diff that fixes the issue.
Do not reintroduce Docker/headless recording unless explicitly requested.
