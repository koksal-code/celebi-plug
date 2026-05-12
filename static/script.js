const emptyGeojson = {
  type: "FeatureCollection",
  features: [],
};

const tokenStorageKey = "celebi-plug_mapbox_token";

// Chat-native bootstrap: an agent can preload the Mapbox public token via
//   http://127.0.0.1:5001/#token=pk.XXX
// Hash fragments are never sent to the server (no logs, no proxy exposure).
// We read it, persist to localStorage, then strip it from the URL so the
// token never lingers in browser history.
(function bootstrapTokenFromHash() {
  if (!location.hash) return;
  const hash = new URLSearchParams(location.hash.slice(1));
  const t = hash.get("token");
  if (!t || !t.startsWith("pk.")) return;
  localStorage.setItem(tokenStorageKey, t);
  hash.delete("token");
  const newHash = hash.toString();
  history.replaceState(
    null,
    "",
    location.pathname + location.search + (newHash ? "#" + newHash : "")
  );
})();

// Server-injected .env fallback: if app.py read MAPBOX_TOKEN=pk.XXX from
// the local .env, it lands here. We seed localStorage from it so an agent
// that writes the .env once gets a fully chat-native install — the welcome
// screen is skipped on the very first open of a fresh browser.
(function bootstrapTokenFromEnv() {
  const envToken = (window.__CELEBI_ENV_TOKEN__ || "").trim();
  if (!envToken.startsWith("pk.")) return;
  if (localStorage.getItem(tokenStorageKey)) return;
  localStorage.setItem(tokenStorageKey, envToken);
})();

const initialMapboxToken = localStorage.getItem(tokenStorageKey) || "";

const input = document.getElementById("geojson-input");
const mapboxTokenInput = document.getElementById("mapbox-token");
const mapboxTokenStudioInput = document.getElementById("mapbox-token-studio");
const applyMapboxTokenBtn = document.getElementById("apply-mapbox-token");
const applyMapboxTokenStudioBtn = document.getElementById("apply-mapbox-token-studio");
const welcomeScreen = document.getElementById("welcome-screen");
const studioScreen = document.getElementById("studio-screen");
const tokenStatusEl = document.getElementById("token-status");
const studioTokenStatusEl = document.getElementById("studio-token-status");
const openSettingsBtn = document.getElementById("open-settings");
const closeSettingsBtn = document.getElementById("close-settings");
const studioSettingsEl = document.getElementById("studio-settings");
const fileNameEl = document.getElementById("file-name");
const featureCountEl = document.getElementById("feature-count");
const geometryTypesEl = document.getElementById("geometry-types");
const statusMessageEl = document.getElementById("status-message");
const uploadBoxEl = document.getElementById("upload-box");
const uploadTitleEl = document.getElementById("upload-title");
const uploadTextEl = document.getElementById("upload-text");
const uploadFileHintEl = document.getElementById("upload-file-hint");
const nearbyListEl = document.getElementById("nearby-list");
const nearbyStatusEl = document.getElementById("nearby-status");
const sourceTabBtns = Array.from(document.querySelectorAll(".source-tab"));
const sourcePaneEls = Array.from(document.querySelectorAll(".source-pane"));
const searchInputEl = document.getElementById("search-input");
const searchGoBtn = document.getElementById("search-go");
const searchStatusEl = document.getElementById("search-status");
const searchRadiusInput = document.getElementById("search-radius");
const pinCoordsInput = document.getElementById("pin-coords");
const pinRadiusInput = document.getElementById("pin-radius");
const pinGoBtn = document.getElementById("pin-go");
const pinPickMapBtn = document.getElementById("pin-pick-map");
const pinStatusEl = document.getElementById("pin-status");
const boxDrawBtn = document.getElementById("box-draw");
const boxStatusEl = document.getElementById("box-status");
const resultModalEl = document.getElementById("result-modal");
const resultVideoEl = document.getElementById("result-video");
const resultMetaEl = document.getElementById("result-meta");
const resultDownloadBtn = document.getElementById("result-download");
const resultRerecordWithPoiBtn = document.getElementById("result-rerecord-with-poi");
const resultRerecordNoPoiBtn = document.getElementById("result-rerecord-no-poi");
const closeResultBtn = document.getElementById("close-result");
const routeStatusEl = document.getElementById("route-status");
const previewRouteBtn = document.getElementById("preview-route");
const recordRouteBtn = document.getElementById("record-route");
const routeProgressEl = document.getElementById("route-progress");
const formatBtns = Array.from(document.querySelectorAll(".format-btn"));
const presetBtns = Array.from(document.querySelectorAll(".preset-btn"));
const mapWrapEl = document.getElementById("map-wrap");
const previewMetaEl = document.getElementById("preview-meta");
const activeShotLabelEl = document.getElementById("active-shot-label");
const scenePoi1El = document.getElementById("scene-poi-1");
const scenePoi2El = document.getElementById("scene-poi-2");

// HUD elements
const hudLatEl = document.getElementById("hud-lat");
const hudLonEl = document.getElementById("hud-lon");
const hudBrgEl = document.getElementById("hud-brg");
const hudPchEl = document.getElementById("hud-pch");
const hudZoomEl = document.getElementById("hud-zoom");
const hudTcEl = document.getElementById("hud-tc");
const hudFrameEl = document.getElementById("hud-frame");
const hudStateEl = document.getElementById("hud-state");
const hudRecLabelEl = document.getElementById("hud-rec-label");
const compassNeedleEl = document.getElementById("compass-needle");
const welcomeClockEl = document.getElementById("welcome-clock");
const footMetaEl = document.getElementById("foot-meta");

const aspectLabels = {
  "16-9": "16:9",
  "9-16": "9:16",
  "1-1": "1:1",
  "4-5": "4:5",
  "21-9": "21:9",
  "4-3": "4:3",
  "3-4": "3:4",
};

const presetLabels = {
  showcase: "Pilot",
  orbit: "Orbit",
  reveal: "Reveal",
  flyover: "Flyover",
  "top-down": "Top-down",
};

// ----- composite canvas for recording with overlay transitions -----
const recordCanvas = document.createElement("canvas");
const recordCtx = recordCanvas.getContext("2d");
let fadeEl = null;

function syncRecordCanvasSize() {
  const m = map && map.getCanvas ? map.getCanvas() : null;
  if (!m) return;
  if (recordCanvas.width !== m.width) recordCanvas.width = m.width;
  if (recordCanvas.height !== m.height) recordCanvas.height = m.height;
}

function drawRecordFrame(overlay) {
  if (!map) return;
  syncRecordCanvasSize();
  const m = map.getCanvas();
  recordCtx.drawImage(m, 0, 0);
  if (overlay && overlay.opacity > 0) {
    recordCtx.globalAlpha = Math.min(overlay.opacity, 1);
    recordCtx.fillStyle = overlay.color;
    recordCtx.fillRect(0, 0, recordCanvas.width, recordCanvas.height);
    recordCtx.globalAlpha = 1;
  }
}

// ============================================================
// i18n — tr / de / en
// ============================================================

const langStorageKey = "celebi-plug_lang";

const translations = {
  tr: {
    "hero.kicker": "[01] görev brifingi",
    "hero.title.line2": "<em>Geo-cinema</em> motoru",
    "hero.lead":
      "GeoJSON'dan sinematik 3D drone çekimi. Mapbox uydu + 3D arazi. Tarayıcıdan 60 saniyelik MP4 (H.264).",
    "step.1": "Mapbox public token (<code>pk.</code>) ekle.",
    "step.2": "GeoJSON dosyanı yükle, POI'lerini seç.",
    "step.3": "Preset ve en-boy oranı seç, kaydet.",
    "step.4": "Videonu indir, paylaş.",
    "token.kicker": "[02] kimlik doğrulama gerekli",
    "token.title": "Mapbox public token",
    "token.body":
      "Harita, 3D arazi ve bina katmanı için kendi Mapbox public token'ınla başlat. Token sunucuya gönderilmez, sadece tarayıcında saklanır.",
    "token.btn": "Başlat",
    "token.btn.update": "Güncelle",
    "token.help.summary": "Token nasıl alınır?",
    "token.help.2": "Access tokens → default public token",
    "token.help.3": "Buraya yapıştır, BAŞLAT'a bas",
    "modal.body":
      "Token yalnızca bu tarayıcıda saklanır. Public token (<code>pk.</code>) gereklidir.",
    "foot.left": "CELEBIPLUG · AÇIK KAYNAK · MIT",
    "foot.mid": "VERİ TARAYICIDAN ÇIKMAZ",
    "status.token.awaiting": "Mapbox public token (pk.) bekleniyor.",
    "status.token.invalid": "Bu public token gibi görünmüyor (pk. ile başlamalı).",
    "status.token.saved": "Mapbox token kaydedildi.",
    "status.token.unauthorized": "Token geçersiz veya yetkisiz.",
    "scene.list.1": "Uzaktan genel",
    "scene.list.2": "Yakın parsel",
    "scene.list.5": "Geri dönüş",
  },
  de: {
    "hero.kicker": "[01] missionsbriefing",
    "hero.title.line2": "<em>Geo-cinema</em>-Engine",
    "hero.lead":
      "Kinematische 3D-Drohnenaufnahmen aus GeoJSON. Mapbox-Satellit + 3D-Gelände. 60-Sekunden-MP4 (H.264) direkt aus dem Browser.",
    "step.1": "Mapbox-Public-Token (<code>pk.</code>) hinzufügen.",
    "step.2": "GeoJSON hochladen, POIs auswählen.",
    "step.3": "Preset und Seitenverhältnis wählen, aufnehmen.",
    "step.4": "Video herunterladen und teilen.",
    "token.kicker": "[02] zugangsdaten erforderlich",
    "token.title": "Mapbox public token",
    "token.body":
      "Bring deinen eigenen Mapbox-Public-Token mit für Karten, 3D-Gelände und Gebäude. Er verlässt niemals deinen Browser — wird nur lokal gespeichert.",
    "token.btn": "Starten",
    "token.btn.update": "Aktualisieren",
    "token.help.summary": "Wie bekomme ich einen Token?",
    "token.help.2": "Access tokens → default public token",
    "token.help.3": "Hier einfügen und STARTEN drücken",
    "modal.body":
      "Der Token wird nur in diesem Browser gespeichert. Ein Public-Token (<code>pk.</code>) ist erforderlich.",
    "foot.left": "CELEBIPLUG · OPEN SOURCE · MIT",
    "foot.mid": "KEINE DATEN VERLASSEN DEN BROWSER",
    "status.token.awaiting": "Warte auf Mapbox-Public-Token (pk.).",
    "status.token.invalid":
      "Das sieht nicht nach einem Public-Token aus (muss mit pk. beginnen).",
    "status.token.saved": "Mapbox-Token gespeichert.",
    "status.token.unauthorized": "Token ungültig oder nicht autorisiert.",
    "scene.list.1": "Übersicht",
    "scene.list.2": "Nahaufnahme",
    "scene.list.5": "Rückkehr",
  },
  en: {
    "hero.kicker": "[01] mission brief",
    "hero.title.line2": "<em>Geo-cinema</em> engine",
    "hero.lead":
      "Cinematic 3D drone shots from GeoJSON. Mapbox satellite + 3D terrain. A 60-second MP4 (H.264) straight from your browser.",
    "step.1": "Add a Mapbox public token (<code>pk.</code>).",
    "step.2": "Upload your GeoJSON, pick POIs.",
    "step.3": "Choose a preset and aspect ratio, capture.",
    "step.4": "Download your video and share.",
    "token.kicker": "[02] credentials required",
    "token.title": "Mapbox public token",
    "token.body":
      "Bring your own Mapbox public token to power maps, 3D terrain, and buildings. It never leaves your browser — only stored locally.",
    "token.btn": "Engage",
    "token.btn.update": "Update",
    "token.help.summary": "How do I get a token?",
    "token.help.2": "Access tokens → default public token",
    "token.help.3": "Paste it here, then ENGAGE",
    "modal.body":
      "The token is only stored in this browser. A public token (<code>pk.</code>) is required.",
    "foot.left": "CELEBIPLUG · OPEN SOURCE · MIT",
    "foot.mid": "NO DATA LEAVES YOUR BROWSER",
    "status.token.awaiting": "Awaiting Mapbox public token (pk.).",
    "status.token.invalid": "That doesn't look like a public token (must start with pk.).",
    "status.token.saved": "Mapbox token saved.",
    "status.token.unauthorized": "Token invalid or unauthorized.",
    "scene.list.1": "Wide overview",
    "scene.list.2": "Close parcel",
    "scene.list.5": "Return",
  },
};

let activeLang = getDefaultLang();

function getDefaultLang() {
  const saved = localStorage.getItem(langStorageKey);
  if (saved && translations[saved]) return saved;
  const browser = (navigator.language || "").slice(0, 2).toLowerCase();
  if (translations[browser]) return browser;
  return "tr";
}

function t(key) {
  return (translations[activeLang] || translations.en)[key] ?? key;
}

function applyTranslations(lang) {
  const dict = translations[lang] || translations.en;
  document.documentElement.lang = lang;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const val = dict[el.dataset.i18n];
    if (typeof val === "string") el.textContent = val;
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const val = dict[el.dataset.i18nHtml];
    if (typeof val === "string") el.innerHTML = val;
  });

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });
}

function setLanguage(lang) {
  if (!translations[lang]) return;
  activeLang = lang;
  localStorage.setItem(langStorageKey, lang);
  applyTranslations(lang);
  // refresh dynamic strings
  if (!localStorage.getItem(tokenStorageKey) && welcomeScreen && !welcomeScreen.classList.contains("hidden")) {
    setTokenStatus(t("status.token.awaiting"));
  }
}

// Pilot's full 5-scene cinematic. The 3-scene "no POI" variant (set via
// setShowcaseSkipPoiScenes) trims to 36s so we don't dwell on synthetic
// fallback targets when the user explicitly opted out of POIs.
const FULL_DURATION = 60000;
const SKIP_POI_DURATION = 36000;
let cinematicDuration = FULL_DURATION;
const fps = 30;
let totalFrames = Math.round((cinematicDuration / 1000) * fps);
let showcaseSkipPoiScenes = false;

function setActiveDuration(ms) {
  cinematicDuration = ms;
  totalFrames = Math.round((cinematicDuration / 1000) * fps);
  const hudDur = document.getElementById("hud-dur");
  if (hudDur) {
    const totalSeconds = Math.round(ms / 1000);
    const mm = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
    const ss = String(totalSeconds % 60).padStart(2, "0");
    hudDur.textContent = `${mm}:${ss}`;
  }
  const presetMeta = document.getElementById("preset-meta");
  if (presetMeta) {
    if (showcaseSkipPoiScenes) presetMeta.textContent = "3 scenes · 36s · 1.2 turns · sparse · no POI";
    else presetMeta.textContent = "5 scenes · 60s · 2 turns · fade-to-black cuts";
  }
}

function setShowcaseSkipPoiScenes(flag) {
  showcaseSkipPoiScenes = Boolean(flag);
  setActiveDuration(showcaseSkipPoiScenes ? SKIP_POI_DURATION : FULL_DURATION);
}

let map = null;
let geojsonLoaded = false;
let routeCoordinates = [];
let routeProgress = 0;
let cinematicAnimationFrame = null;
let isRecording = false;
let mediaRecorder = null;
let recordedChunks = [];
let activeAspect = "16-9";
let activePreset = "showcase";

let shotMeta = {
  center: [35, 39],
  bounds: null,
  span: 0.02,
  closeZoom: 16.5,
  farZoom: 14.5,
  pois: [],
};

let nearbyPois = [];
let selectedPoiIndexes = [];
let poiMarkers = [];

init();

async function init() {
  applyTranslations(activeLang);
  fadeEl = document.getElementById("viewfinder-fade");

  mapboxTokenInput.value = initialMapboxToken;
  mapboxTokenStudioInput.value = initialMapboxToken;

  startWelcomeClock();

  if (initialMapboxToken) {
    await openStudioWithToken(initialMapboxToken);
  } else {
    setTokenStatus(t("status.token.awaiting"));
    welcomeScreen.classList.remove("hidden");
    studioScreen.classList.add("hidden");
  }

  bindUi();
  exposeAgentApi();
  if (map) await maybeRunAutopilot();
}

function startWelcomeClock() {
  if (!welcomeClockEl) return;
  const pad = (n) => String(n).padStart(2, "0");
  const tick = () => {
    const now = new Date();
    welcomeClockEl.textContent =
      `${now.getUTCFullYear()}.${pad(now.getUTCMonth() + 1)}.${pad(now.getUTCDate())} · ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`;
  };
  tick();
  setInterval(tick, 1000);
}

function bindUi() {
  input.addEventListener("change", handleFileUpload);
  recordRouteBtn.addEventListener("click", uiRecord);
  previewRouteBtn.addEventListener("click", togglePreview);
  bindResultModal();
  applyMapboxTokenBtn.addEventListener("click", () => onTokenSubmit(mapboxTokenInput.value));
  applyMapboxTokenStudioBtn.addEventListener("click", () => onTokenSubmit(mapboxTokenStudioInput.value));
  openSettingsBtn.addEventListener("click", openSettings);
  closeSettingsBtn.addEventListener("click", closeSettings);
  studioSettingsEl.addEventListener("click", (event) => {
    if (event.target.dataset.closeSettings !== undefined) {
      closeSettings();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !studioSettingsEl.classList.contains("hidden")) {
      closeSettings();
    }
  });

  // Enter key submits token from welcome and studio inputs
  [mapboxTokenInput, mapboxTokenStudioInput].forEach((el) => {
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        onTokenSubmit(el.value);
      }
    });
  });

  formatBtns.forEach((button) => {
    button.addEventListener("click", () => {
      activeAspect = button.dataset.aspect || "16-9";
      formatBtns.forEach((btn) => btn.classList.toggle("active", btn === button));
      updateCanvasLayout();
    });
  });

  presetBtns.forEach((button) => {
    button.addEventListener("click", () => {
      activePreset = button.dataset.preset || "showcase";
      presetBtns.forEach((btn) => btn.classList.toggle("active", btn === button));
      updateCanvasLayout();
      resetVisualState();
    });
  });

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
  });

  sourceTabBtns.forEach((btn) => {
    btn.addEventListener("click", () => selectSourceTab(btn.dataset.sourceTab));
  });

  if (searchGoBtn) {
    searchGoBtn.addEventListener("click", () => runSearch(searchInputEl.value));
    searchInputEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runSearch(searchInputEl.value);
      }
    });
  }

  if (pinGoBtn) {
    pinGoBtn.addEventListener("click", () => runPinFromInput());
    pinCoordsInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runPinFromInput();
      }
    });
  }
  if (pinPickMapBtn) {
    pinPickMapBtn.addEventListener("click", () => {
      if (pinPickArmed) disarmPinPick();
      else armPinPick();
    });
  }

  if (boxDrawBtn) {
    boxDrawBtn.addEventListener("click", () => {
      if (boxDrawArmed) disarmBboxDraw();
      else armBboxDraw();
    });
  }
}

async function onTokenSubmit(rawToken) {
  const token = rawToken.trim();
  if (!token.startsWith("pk.")) {
    setTokenStatus(t("status.token.invalid"));
    return;
  }
  localStorage.setItem(tokenStorageKey, token);
  mapboxTokenInput.value = token;
  mapboxTokenStudioInput.value = token;
  setTokenStatus(t("status.token.saved"));
  closeSettings();
  await openStudioWithToken(token);
}

async function openStudioWithToken(token) {
  if (map) return;

  mapboxgl.accessToken = token;

  welcomeScreen.classList.add("hidden");
  studioScreen.classList.remove("hidden");
  document.body.classList.add("studio-active");

  await initializeMap();
  installMapPinHandler();
  updateCanvasLayout();
  setRouteControls(false, "awaiting source");
}

function initializeMap() {
  return new Promise((resolve, reject) => {
    try {
      map = new mapboxgl.Map({
        container: "map",
        style: "mapbox://styles/mapbox/satellite-streets-v12",
        center: shotMeta.center,
        zoom: 3.2,
        pitch: 0,
        bearing: 0,
        antialias: true,
        preserveDrawingBuffer: true,
        attributionControl: false,
      });

      map.on("load", () => {
        try {
          if (!map.getSource("mapbox-dem")) {
            map.addSource("mapbox-dem", {
              type: "raster-dem",
              url: "mapbox://mapbox.mapbox-terrain-dem-v1",
              tileSize: 512,
              maxzoom: 14,
            });
          }
          map.setTerrain({ source: "mapbox-dem", exaggeration: 1.4 });
          // Vacuum-clean sky. No clouds, no haze. Fog pushed far away and made
          // nearly transparent; the high-color is the deep-blue night sky we
          // actually want to see, and space-color seals it into black.
          map.setFog({
            range: [14, 50],
            "horizon-blend": 0.015,
            color: "rgba(255, 255, 255, 0.04)",
            "high-color": "rgb(10, 22, 42)",
            "space-color": "rgb(2, 3, 8)",
            "star-intensity": 0.55,
          });
          addBuildingsLayer();
        } catch (error) {
          console.warn("Terrain/buildings setup error:", error);
        }
        resolve();
      });

      map.on("error", (event) => {
        const errMessage = event?.error?.message || "";
        if (errMessage.toLowerCase().includes("unauthorized") || errMessage.includes("401")) {
          setTokenStatus(t("status.token.unauthorized"));
        }
      });
    } catch (error) {
      reject(error);
    }
  });
}

function addBuildingsLayer() {
  if (map.getLayer("3d-buildings")) return;
  const layers = map.getStyle().layers || [];
  const labelLayer = layers.find(
    (layer) => layer.type === "symbol" && layer.layout && layer.layout["text-field"],
  );

  map.addLayer(
    {
      id: "3d-buildings",
      source: "composite",
      "source-layer": "building",
      filter: ["==", ["get", "extrude"], "true"],
      type: "fill-extrusion",
      minzoom: 14,
      paint: {
        "fill-extrusion-color": "#9aa3b0",
        "fill-extrusion-height": ["get", "height"],
        "fill-extrusion-base": ["get", "min_height"],
        "fill-extrusion-opacity": 0.85,
      },
    },
    labelLayer ? labelLayer.id : undefined,
  );
}

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const geojson = JSON.parse(text);
    await loadGeoJsonObject(geojson, file.name);
  } catch (error) {
    clearMapLayer();
    setUploadState("error", `failed: ${file.name}`);
    setStatus(`error: ${error.message}`, true);
    setRouteControls(false, "awaiting source");
  }
}

// Shared pipeline for any GeoJSON source: file upload, autopilot URL params,
// window.celebiPlug API, or a future on-map pin tool.
async function loadGeoJsonObject(geojson, sourceLabel) {
  setUploadState("loading", "loading...");
  try {
    validateGeoJson(geojson);
    const normalized = normalizeGeoJson(geojson);
    geojsonLoaded = true;

    // Reset Pilot timing on every new source load. autopilot's poi= handler
    // re-applies the right mode immediately after, so URL flows stay correct.
    setShowcaseSkipPoiScenes(false);

    clearPolygonHandles();
    showGeoJsonOnMap(normalized);
    setupFlightRoute(normalized);
    updateSummary(sourceLabel, normalized);
    setUploadState("loaded", sourceLabel);

    // Synthetic (pin / search / box) shapes are user-resizable — drop
    // draggable corner handles so the user can dial framing without
    // re-running the whole input flow.
    const firstProps = normalized.features?.[0]?.properties || {};
    const isSynthetic = Boolean(
      firstProps.celebiPlugSyntheticPin ||
      firstProps.celebiPlugSearch ||
      firstProps.celebiPlugBox,
    );
    if (isSynthetic) {
      const b = getGeoJsonBounds(normalized);
      if (b) {
        currentSyntheticBounds = b;
        placePolygonHandles(b);
      }
    } else {
      currentSyntheticBounds = null;
    }

    setStatus("source loaded · scanning poi...");
    await scanNearbyPois();
    setStatus("source loaded");
    setRouteControls(true, `${routeCoordinates.length || 2} nokta hazir`);
  } catch (error) {
    clearMapLayer();
    clearPolygonHandles();
    setUploadState("error", `failed: ${sourceLabel}`);
    setStatus(`error: ${error.message}`, true);
    setRouteControls(false, "awaiting source");
    throw error;
  }
}

// Build a small square polygon around a lon/lat — used by autopilot URL
// params and the window.celebiPlug API to drop the agent on a target without
// requiring the user to author a GeoJSON file.
function makeSquareGeoJson([lon, lat], radiusMeters = 50) {
  const mPerDegLat = 111320;
  const mPerDegLng = 111320 * Math.cos((lat * Math.PI) / 180);
  const dLat = radiusMeters / mPerDegLat;
  const dLng = radiusMeters / Math.max(mPerDegLng, 1);
  const ring = [
    [lon - dLng, lat - dLat],
    [lon + dLng, lat - dLat],
    [lon + dLng, lat + dLat],
    [lon - dLng, lat + dLat],
    [lon - dLng, lat - dLat],
  ];
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { celebiPlugSyntheticPin: true, radiusMeters },
        geometry: { type: "Polygon", coordinates: [ring] },
      },
    ],
  };
}

function validateGeoJson(data) {
  const validTypes = [
    "FeatureCollection", "Feature", "Point", "MultiPoint",
    "LineString", "MultiLineString", "Polygon", "MultiPolygon", "GeometryCollection",
  ];
  if (!data || typeof data !== "object" || !validTypes.includes(data.type)) {
    throw new Error("invalid geojson");
  }
}

function normalizeGeoJson(geojson) {
  if (geojson.type === "FeatureCollection") return geojson;
  if (geojson.type === "Feature") return { type: "FeatureCollection", features: [geojson] };
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: geojson }],
  };
}

function showGeoJsonOnMap(geojson) {
  if (!map.isStyleLoaded()) {
    map.once("idle", () => showGeoJsonOnMap(geojson));
    return;
  }
  const sourceId = "uploaded-geojson";

  ["uploaded-fill-extrude", "uploaded-line", "uploaded-point"].forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource(sourceId)) map.removeSource(sourceId);

  map.addSource(sourceId, { type: "geojson", data: geojson });

  map.addLayer({
    id: "uploaded-fill-extrude",
    type: "fill-extrusion",
    source: sourceId,
    filter: ["any", ["==", ["geometry-type"], "Polygon"], ["==", ["geometry-type"], "MultiPolygon"]],
    paint: {
      "fill-extrusion-color": "#ef4444",
      "fill-extrusion-opacity": 0.5,
      "fill-extrusion-height": 90,
      "fill-extrusion-base": 0,
    },
  });

  map.addLayer({
    id: "uploaded-line",
    type: "line",
    source: sourceId,
    filter: [
      "any",
      ["==", ["geometry-type"], "LineString"],
      ["==", ["geometry-type"], "MultiLineString"],
      ["==", ["geometry-type"], "Polygon"],
      ["==", ["geometry-type"], "MultiPolygon"],
    ],
    paint: { "line-color": "#ef4444", "line-width": 2.8 },
  });

  map.addLayer({
    id: "uploaded-point",
    type: "circle",
    source: sourceId,
    filter: ["any", ["==", ["geometry-type"], "Point"], ["==", ["geometry-type"], "MultiPoint"]],
    paint: {
      "circle-color": "#ef4444",
      "circle-radius": 7,
      "circle-stroke-color": "#07070a",
      "circle-stroke-width": 2,
    },
  });

  const bounds = getGeoJsonBounds(geojson);
  if (bounds) {
    // Slowly settle into the canonical wide-shot angle so preview ≈ recording start.
    map.fitBounds(
      [[bounds.west, bounds.south], [bounds.east, bounds.north]],
      {
        padding: 120,
        duration: 2400,
        pitch: WIDE_SHOT_PITCH,
        bearing: WIDE_SHOT_BEARING,
        essential: true,
      },
    );
  }
}

function clearMapLayer() {
  if (!map) return;
  ["uploaded-fill-extrude", "uploaded-line", "uploaded-point"].forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource("uploaded-geojson")) map.removeSource("uploaded-geojson");
  geojsonLoaded = false;
  resetNearbyPois("awaiting source");
}

function setupFlightRoute(geojson) {
  routeCoordinates = extractRouteCoordinates(geojson);
  shotMeta = calculateShotMeta(geojson, routeCoordinates);
  routeProgress = 0;
  updateRouteProgressLayer();
  updateScenePoiLabels([]);
}

function calculateShotMeta(geojson, route) {
  const bounds = getGeoJsonBounds(geojson);
  const fallbackCenter = route[0] || [35, 39];
  const west = bounds ? bounds.west : fallbackCenter[0] - 0.01;
  const east = bounds ? bounds.east : fallbackCenter[0] + 0.01;
  const south = bounds ? bounds.south : fallbackCenter[1] - 0.01;
  const north = bounds ? bounds.north : fallbackCenter[1] + 0.01;
  const span = Math.max(Math.abs(east - west), Math.abs(north - south), 0.0005);
  // Parcel zoom from area (matches the v2 source logic).
  const parcelZoom = getParcelBaseZoom(geojson);
  const closeZoom = parcelZoom;
  const farZoom = parcelZoom - 3; // V2 scene 1 zoomOffset
  return {
    center: [(west + east) / 2, (south + north) / 2],
    bounds: { west, east, south, north },
    span,
    parcelZoom,
    closeZoom,
    farZoom,
    pois: [],
  };
}

// Area-based parcel zoom — bigger area → camera pulls further back.
// Extended past the v2 cap of z15 so city- and district-scale shots
// frame correctly instead of clipping into the ground at 50,000 m².
function getZoomFromArea(areaM2) {
  if (areaM2 <= 300) return 19;
  if (areaM2 <= 600) return 18.5;
  if (areaM2 <= 1000) return 18;
  if (areaM2 <= 2000) return 17.5;
  if (areaM2 <= 5000) return 17;
  if (areaM2 <= 10000) return 16.5;
  if (areaM2 <= 25000) return 16;
  if (areaM2 <= 50000) return 15.5;
  if (areaM2 <= 200000) return 15;
  if (areaM2 <= 500000) return 14.5;
  if (areaM2 <= 1_500_000) return 14;
  if (areaM2 <= 5_000_000) return 13;
  if (areaM2 <= 20_000_000) return 12;
  return 11;
}

function getParcelBaseZoom(data) {
  try {
    const feat = data?.features?.[0];
    if (!feat?.geometry) return 16;
    const geom = feat.geometry;
    let ring = [];
    if (geom.type === "Polygon" && geom.coordinates?.[0]) ring = geom.coordinates[0];
    else if (geom.type === "MultiPolygon" && geom.coordinates?.[0]?.[0]) ring = geom.coordinates[0][0];
    if (ring.length < 3) return 16;

    const centerLat = ring.reduce((s, c) => s + (c[1] || 0), 0) / ring.length;
    const degToRad = Math.PI / 180;
    const mPerDegLat = 111320;
    const mPerDegLng = 111320 * Math.cos(centerLat * degToRad);

    let area = 0;
    for (let i = 0; i < ring.length; i += 1) {
      const j = (i + 1) % ring.length;
      const xi = (ring[i][0] || 0) * mPerDegLng;
      const yi = (ring[i][1] || 0) * mPerDegLat;
      const xj = (ring[j][0] || 0) * mPerDegLng;
      const yj = (ring[j][1] || 0) * mPerDegLat;
      area += xi * yj - xj * yi;
    }
    area = Math.abs(area) / 2;
    return getZoomFromArea(area);
  } catch (_e) {
    return 16;
  }
}

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }

function extractRouteCoordinates(geojson) {
  for (const feature of geojson.features) {
    const route = getRouteFromGeometry(feature.geometry);
    if (route.length >= 2) return route;
  }
  const bounds = getGeoJsonBounds(geojson);
  if (!bounds) return [];
  return [
    [bounds.west, bounds.south],
    [bounds.east, bounds.south],
    [bounds.east, bounds.north],
    [bounds.west, bounds.north],
    [bounds.west, bounds.south],
  ];
}

function getRouteFromGeometry(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return cleanRouteCoordinates(geometry.coordinates);
  if (geometry.type === "MultiLineString") return cleanRouteCoordinates(geometry.coordinates.flat());
  if (geometry.type === "Polygon") return cleanRouteCoordinates((geometry.coordinates && geometry.coordinates[0]) || []);
  if (geometry.type === "MultiPolygon") {
    return cleanRouteCoordinates(
      (geometry.coordinates && geometry.coordinates[0] && geometry.coordinates[0][0]) || [],
    );
  }
  if (geometry.type === "GeometryCollection") {
    for (const child of geometry.geometries || []) {
      const route = getRouteFromGeometry(child);
      if (route.length >= 2) return route;
    }
  }
  return [];
}

function cleanRouteCoordinates(coordinates) {
  return (coordinates || [])
    .filter((coord) => Array.isArray(coord) && Number.isFinite(coord[0]) && Number.isFinite(coord[1]))
    .map((coord) => [coord[0], coord[1]]);
}

function getGeoJsonBounds(geojson) {
  const coordinates = [];
  geojson.features.forEach((feature) => collectCoordinates(feature.geometry, coordinates));
  if (!coordinates.length) return null;
  let west = coordinates[0][0], east = coordinates[0][0];
  let south = coordinates[0][1], north = coordinates[0][1];
  coordinates.forEach((coord) => {
    west = Math.min(west, coord[0]);
    east = Math.max(east, coord[0]);
    south = Math.min(south, coord[1]);
    north = Math.max(north, coord[1]);
  });
  return { west, east, south, north };
}

function collectCoordinates(geometry, output) {
  if (!geometry) return;
  if (geometry.type === "GeometryCollection") {
    (geometry.geometries || []).forEach((child) => collectCoordinates(child, output));
    return;
  }
  const walk = (value) => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1])) {
      output.push([value[0], value[1]]);
      return;
    }
    value.forEach(walk);
  };
  walk(geometry.coordinates);
}

function updateSummary(fileName, geojson) {
  const features = Array.isArray(geojson.features) ? geojson.features : [];
  const geometryTypes = new Set();
  features.forEach((feature) => collectGeometryTypes(feature.geometry, geometryTypes));
  fileNameEl.textContent = fileName;
  featureCountEl.textContent = String(features.length);
  geometryTypesEl.textContent = geometryTypes.size ? Array.from(geometryTypes).sort().join(", ") : "-";
  if (footMetaEl) {
    footMetaEl.textContent = `${fileName} · ${features.length} feature${features.length === 1 ? "" : "s"} · ${
      geometryTypes.size ? Array.from(geometryTypes).join(", ") : "-"
    }`;
  }
}

function collectGeometryTypes(geometry, geometryTypes) {
  if (!geometry || !geometry.type) return;
  if (geometry.type === "GeometryCollection") {
    (geometry.geometries || []).forEach((child) => collectGeometryTypes(child, geometryTypes));
    return;
  }
  geometryTypes.add(geometry.type);
}

function setStatus(message, isError = false) {
  statusMessageEl.textContent = message;
  statusMessageEl.classList.toggle("error", isError);
}

function setUploadState(state, text) {
  uploadBoxEl.classList.toggle("is-loading", state === "loading");
  uploadBoxEl.classList.toggle("is-loaded", state === "loaded");
  uploadBoxEl.classList.toggle("is-error", state === "error");
  uploadTitleEl.textContent = state === "loaded" ? "Source ready" : "Drop geojson";
  uploadTextEl.textContent = state === "loaded" ? "rendered · in scene" : ".geojson · .json";
  uploadFileHintEl.textContent = text;
  uploadFileHintEl.title = text;
}

function resetNearbyPois(statusText = "awaiting source") {
  nearbyPois = [];
  selectedPoiIndexes = [];
  renderPoiMarkers([]);
  updateScenePoiLabels([]);
  renderNearbyPois([], statusText);
}

function getSelectedPois() {
  return selectedPoiIndexes.map((index) => nearbyPois[index]).filter(Boolean);
}

async function fetchOverpassJson(query) {
  const endpoints = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
  ];
  for (const url of endpoints) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 16000);
    try {
      const response = await fetch(url, {
        method: "POST",
        body: query,
        headers: { "Content-Type": "text/plain;charset=UTF-8" },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (!response.ok) continue;
      return JSON.parse(await response.text());
    } catch (error) {
      clearTimeout(timeoutId);
    }
  }
  return { elements: [] };
}

async function fetchNearbyOsmPois(center, radius = 5000) {
  const [lon, lat] = center;
  const query = `
    [out:json][timeout:20];
    (
      nwr["name"]["shop"](around:${radius},${lat},${lon});
      nwr["name"]["amenity"~"cafe|restaurant|bar|pub|fast_food|bakery|pharmacy|hospital|clinic|bank|atm|fuel|marketplace|cinema|theatre|library|college|university"](around:${radius},${lat},${lon});
      nwr["name"]["tourism"~"hotel|guest_house|museum|attraction|viewpoint"](around:${radius},${lat},${lon});
      nwr["name"]["leisure"~"park|stadium|sports_centre|fitness_centre"](around:${radius},${lat},${lon});
    );
    out tags center 200;
  `;
  const data = await fetchOverpassJson(query);
  return (data.elements || []).map((el, i) => ({
    name: el.tags?.name || el.tags?.amenity || el.tags?.shop || `OSM POI ${i + 1}`,
    coordinates: [el.lon ?? el.center?.lon, el.lat ?? el.center?.lat],
    distanceMeters: getDistanceMeters(center, [el.lon ?? el.center?.lon, el.lat ?? el.center?.lat]),
    source: "osm",
  }));
}

async function scanNearbyPois() {
  if (!geojsonLoaded) {
    resetNearbyPois("awaiting source");
    return;
  }
  renderNearbyPois([], "scanning...");
  let scanned = [];
  try {
    const pois = await fetchNearbyOsmPois(shotMeta.center, 5000);
    scanned = normalizePois(pois, shotMeta.center);
  } catch (error) {
    scanned = [];
  }
  nearbyPois = scanned.slice(0, 30);
  selectedPoiIndexes = [];
  shotMeta.pois = [];
  renderPoiMarkers([]);
  updateScenePoiLabels([]);
  renderNearbyPois(
    nearbyPois,
    nearbyPois.length ? `${nearbyPois.length} hit · pick up to 2` : "no poi within 5km",
  );
}

function normalizePois(pois, center) {
  const seen = new Set();
  return pois
    .filter(
      (poi) =>
        poi &&
        Array.isArray(poi.coordinates) &&
        Number.isFinite(poi.coordinates[0]) &&
        Number.isFinite(poi.coordinates[1]),
    )
    .map((poi) => ({
      ...poi,
      name: poi.name || "unknown",
      distanceMeters: Number.isFinite(poi.distanceMeters)
        ? poi.distanceMeters
        : getDistanceMeters(center, poi.coordinates),
    }))
    .filter((poi) => {
      const key = `${poi.name.toLocaleLowerCase("tr-TR")}-${poi.coordinates.map((v) => v.toFixed(4)).join(",")}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.distanceMeters - b.distanceMeters);
}

function renderNearbyPois(pois, statusText) {
  nearbyStatusEl.textContent = statusText;
  nearbyListEl.replaceChildren();

  if (!pois.length) {
    const item = document.createElement("li");
    item.className = "poi-empty";
    item.textContent = statusText;
    nearbyListEl.appendChild(item);
    return;
  }

  pois.forEach((poi, index) => {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    const badge = document.createElement("span");
    const actions = document.createElement("div");
    const selectBtn = document.createElement("button");

    const isSelected = selectedPoiIndexes.includes(index);
    if (isSelected) item.classList.add("is-selected");

    name.textContent = poi.name;
    badge.textContent = formatDistance(poi.distanceMeters);
    actions.className = "poi-actions";

    selectBtn.type = "button";
    selectBtn.className = "poi-action-btn";
    selectBtn.textContent = isSelected ? `POI ${selectedPoiIndexes.indexOf(index) + 1} clear` : "Mark";
    selectBtn.addEventListener("click", () => {
      if (selectedPoiIndexes.includes(index)) {
        selectedPoiIndexes = selectedPoiIndexes.filter((value) => value !== index);
      } else if (selectedPoiIndexes.length < 2) {
        selectedPoiIndexes = [...selectedPoiIndexes, index];
      } else {
        selectedPoiIndexes = [selectedPoiIndexes[1], index];
      }
      shotMeta.pois = getSelectedPois();
      renderPoiMarkers(shotMeta.pois);
      updateScenePoiLabels(shotMeta.pois);
      renderNearbyPois(nearbyPois, nearbyStatusEl.textContent);
      if (activeShotLabelEl) {
        activeShotLabelEl.textContent = computeShotLabel().toUpperCase();
      }
    });

    actions.append(selectBtn);
    item.append(name, badge, actions);
    nearbyListEl.appendChild(item);
  });
}

function renderPoiMarkers(pois) {
  poiMarkers.forEach((marker) => marker.remove());
  poiMarkers = [];
  pois.forEach((poi) => {
    const el = document.createElement("div");
    el.className = "poi-marker";
    el.title = poi.name;
    const marker = new mapboxgl.Marker({ element: el, anchor: "bottom" })
      .setLngLat(poi.coordinates)
      .setPopup(new mapboxgl.Popup({ offset: 12 }).setText(poi.name))
      .addTo(map);
    poiMarkers.push(marker);
  });
}

function updateScenePoiLabels(pois) {
  if (scenePoi1El) scenePoi1El.textContent = pois[0]?.name || "POI 1";
  if (scenePoi2El) scenePoi2El.textContent = pois[1]?.name || "POI 2";
}

function formatDistance(distanceMeters) {
  if (!Number.isFinite(distanceMeters)) return "";
  if (distanceMeters >= 1000) return `${(distanceMeters / 1000).toFixed(1)}km`;
  return `${Math.max(Math.round(distanceMeters), 1)}m`;
}

function computeShotLabel() {
  const base = presetLabels[activePreset] || "Showcase";
  if (activePreset === "showcase") {
    const n = shotMeta.pois.length;
    if (n === 0) return `${base} · orbit`;
    if (n === 1) return `${base} · 1 poi`;
    return `${base} · 2 poi`;
  }
  return base;
}

function updateCanvasLayout() {
  if (activeShotLabelEl) {
    activeShotLabelEl.textContent = computeShotLabel().toUpperCase();
  }
  if (previewMetaEl) previewMetaEl.textContent = aspectLabels[activeAspect] || "16:9";
  // Never restyle the viewfinder or resize the canvas while recording —
  // both invalidate the MediaRecorder stream mid-capture.
  if (mediaRecorder && mediaRecorder.state === "recording") return;
  mapWrapEl.className = `viewfinder aspect-${activeAspect}`;
  window.setTimeout(() => map?.resize?.(), 100);
}

function setTokenStatus(message) {
  tokenStatusEl.textContent = message;
  studioTokenStatusEl.textContent = message;
}

function openSettings() { studioSettingsEl.classList.remove("hidden"); }
function closeSettings() { studioSettingsEl.classList.add("hidden"); }

function setRouteControls(enabled, statusText) {
  recordRouteBtn.disabled = !enabled || isRecording;
  previewRouteBtn.disabled = !enabled || isRecording;
  if (routeStatusEl) routeStatusEl.textContent = statusText;
  routeProgressEl.style.width = `${Math.round(routeProgress * 100)}%`;
  if (hudStateEl && !isRecording) hudStateEl.textContent = enabled ? "READY" : "STANDBY";
}

function updateRouteProgressLayer() {
  routeProgressEl.style.width = `${Math.round(routeProgress * 100)}%`;
}

function lerp(a, b, t) { return a + (b - a) * t; }
function lerpLngLat(a, b, t) { return [lerp(a[0], b[0], t), lerp(a[1], b[1], t)]; }
function easeInOutCubic(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
function easeInOutQuint(t) { return t < 0.5 ? 16 * t * t * t * t * t : 1 - Math.pow(-2 * t + 2, 5) / 2; }

function interpolateKeyframes(keyframes, progress, easing = easeInOutQuint) {
  for (let i = 0; i < keyframes.length - 1; i += 1) {
    const a = keyframes[i];
    const b = keyframes[i + 1];
    if (progress <= b.t || i === keyframes.length - 2) {
      const local = clamp((progress - a.t) / (b.t - a.t || 1), 0, 1);
      const e = easing(local);
      return {
        center: lerpLngLat(a.center, b.center, e),
        zoom: lerp(a.zoom, b.zoom, e),
        pitch: lerp(a.pitch, b.pitch, e),
        bearing: a.bearing + (b.bearing - a.bearing) * e,
      };
    }
  }
  const last = keyframes[keyframes.length - 1];
  return { center: last.center, zoom: last.zoom, pitch: last.pitch, bearing: last.bearing };
}

function headingFromTo(a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  return (Math.atan2(dx, dy) * 180) / Math.PI;
}

function getFallbackPoi(index) {
  const dir = index === 0 ? 1 : -1;
  const off = Math.max(shotMeta.span * 0.45, 0.002);
  return {
    coordinates: [shotMeta.center[0] + off * dir, shotMeta.center[1] + off * 0.7 * dir],
  };
}

function getCinematicScene(progress) {
  const t = clamp(progress, 0, 1);
  switch (activePreset) {
    case "orbit": return orbitScene(t);
    case "reveal": return revealScene(t);
    case "flyover": return flyoverScene(t);
    case "top-down": return topDownScene(t);
    case "showcase":
    default: return showcaseScene(t);
  }
}

// ============================================================
// Cinematic presets — keyframe driven, slow quintic easing.
//
// Design rules:
//  • Bearing is monotonic — the camera always orbits, never reverses.
//  • Every wide/establishing keyframe uses the SAME pitch and the SAME
//    framing offset (WIDE_SHOT_PITCH, WIDE_SHOT_BEARING_*), so the
//    opening and closing of every shot look like the same drone angle.
//  • All transitions go through interpolateKeyframes with quintic
//    easing — no jump cuts, just slow glides.
//  • showcaseScene auto-adapts to the number of selected POIs:
//      0 POIs → pure orbit around the parcel (no synthetic targets)
//      1 POI  → wide → orbit POI → wide
//      2 POIs → wide → POI1 → POI2 → wide
// ============================================================

const WIDE_SHOT_PITCH = 35;
const WIDE_SHOT_BEARING = -30;   // canonical start bearing for any shot
const WIDE_SHOT_BEARING_END = 330; // end bearing — one full 360° orbit

// ============================================================
// Showcase / Pilot — ported VERBATIM from the v2 source's
// `getSceneState`. 60-second video, 2 full rotations (720°),
// 5 equal-weight scenes with fade-to-black transitions between
// them (fadeDuration 0.02 = ~1.2s each). Polygon opacity varies
// per scene to spotlight the parcel only when it's the subject.
// ============================================================

// Each scene carries its target (which point the camera frames) and its
// polygon opacity. The "no POI" mode filters out target=poi1/poi2 scenes
// and ends up with three center-locked scenes (1, 2, 5).
const SHOWCASE_CONFIG = {
  rotationTurns: 2,
  fadeDuration: 0.02,
  scenes: [
    { pitch: 60, zoomOffset: -3, weight: 1, target: "center", polygonOpacity: 0.45 }, // 1: far
    { pitch: 75, zoomOffset: 0,  weight: 1, target: "center", polygonOpacity: 0.70 }, // 2: close, steep
    { pitch: 60, zoomOffset: 0,  weight: 1, target: "poi1",   polygonOpacity: 0.15 }, // 3: POI 1
    { pitch: 60, zoomOffset: 0,  weight: 1, target: "poi2",   polygonOpacity: 0.15 }, // 4: POI 2
    { pitch: 60, zoomOffset: 0,  weight: 1, target: "center", polygonOpacity: 0.60 }, // 5: return
  ],
};
const DEFAULT_POLYGON_OPACITY = 0.5;

function easeInOutCubicV2(x) {
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

function showcaseScene(progress) {
  const cfg = SHOWCASE_CONFIG;
  const closeZoom = shotMeta.parcelZoom;

  // In skip-POI mode, drop the two POI scenes (3 & 4) and keep the
  // three center-locked beats (1, 2, 5). 36s version with proportional
  // rotation (1.2 turns vs the full 2) keeps angular velocity constant.
  const allScenes = cfg.scenes;
  const sc = showcaseSkipPoiScenes
    ? allScenes.filter((s) => s.target === "center")
    : allScenes;
  const numScenes = sc.length;
  const rotationTurns = cfg.rotationTurns * (numScenes / allScenes.length);
  const totalRotation = rotationTurns * 360;
  const fadeDur = cfg.fadeDuration;

  const centerLngLat = shotMeta.center; // [lng, lat]
  const poi1 = shotMeta.pois[0]
    ? shotMeta.pois[0].coordinates
    : [centerLngLat[0] + 0.005, centerLngLat[1] + 0.005];
  const poi2 = shotMeta.pois[1]
    ? shotMeta.pois[1].coordinates
    : [centerLngLat[0] - 0.005, centerLngLat[1] - 0.005];

  const resolveTarget = (scene) => {
    if (scene.target === "poi1") return poi1;
    if (scene.target === "poi2") return poi2;
    return centerLngLat;
  };

  const bearing = (progress * totalRotation) % 360;

  // Compute scene boundaries (timing fractions of full duration).
  const totalWeight = sc.reduce((s, c) => s + c.weight, 0);
  const fadeCount = Math.max(numScenes - 1, 0);
  const availableTime = 1 - fadeCount * fadeDur;
  const durations = sc.map((c) => (c.weight / totalWeight) * availableTime);
  const ends = [];
  const starts = [0];
  let cursor = 0;
  for (let i = 0; i < numScenes; i += 1) {
    cursor += durations[i];
    ends.push(cursor);
    if (i < numScenes - 1) {
      cursor += fadeDur;
      starts.push(cursor);
    }
  }

  let center = centerLngLat;
  let zoom = closeZoom;
  let fade = 0;
  let polygonOpacity = 0.06;
  let activeIdx = 0;
  let found = false;

  for (let i = 0; i < numScenes; i += 1) {
    if (progress < ends[i]) {
      center = resolveTarget(sc[i]);
      if (i === numScenes - 1) {
        // Final scene may pull back if zoomOffset differs from 0.
        const returnT = (progress - starts[i]) / (ends[i] - starts[i]);
        const farZ = closeZoom + sc[i].zoomOffset;
        zoom = closeZoom + (farZ - closeZoom) * easeInOutCubicV2(returnT);
      } else {
        zoom = closeZoom + sc[i].zoomOffset;
      }
      polygonOpacity = sc[i].polygonOpacity;
      activeIdx = i;
      // fade-out at the tail end of the scene → goes black
      if (progress > ends[i] - fadeDur) {
        fade = easeInOutCubicV2((progress - (ends[i] - fadeDur)) / fadeDur);
      }
      found = true;
      break;
    }
    if (i < numScenes - 1 && progress < starts[i + 1]) {
      // fully in transition between scene i and i+1 — already at next position
      // (snapped under cover of darkness), fading back in
      center = resolveTarget(sc[i + 1]);
      zoom = closeZoom + sc[i + 1].zoomOffset;
      fade = 1 - easeInOutCubicV2((progress - ends[i]) / fadeDur);
      polygonOpacity = sc[i + 1].polygonOpacity;
      activeIdx = i;
      found = true;
      break;
    }
  }
  if (!found) {
    center = centerLngLat;
    zoom = closeZoom + sc[numScenes - 1].zoomOffset;
    polygonOpacity = 0.30;
    activeIdx = numScenes - 1;
  }

  // Pitch follows the upcoming scene during a fade.
  let finalPitch = sc[activeIdx].pitch;
  for (let i = 0; i < numScenes - 1; i += 1) {
    if (progress >= ends[i] && progress < starts[i + 1]) {
      finalPitch = sc[i + 1].pitch;
      break;
    }
  }

  return { center, zoom, pitch: finalPitch, bearing, fade, polygonOpacity };
}

function orbitScene(progress) {
  // Pure orbit. Slow zoom breath in/out, gentle pitch breath, monotonic bearing
  // from the canonical wide-shot angle through a full 360°.
  const easedZoom = easeInOutQuint(progress);
  const breath = Math.sin(progress * Math.PI);
  return {
    center: shotMeta.center,
    zoom: lerp(shotMeta.farZoom - 0.4, shotMeta.closeZoom - 0.6, easedZoom),
    pitch: WIDE_SHOT_PITCH + breath * 28,
    bearing: WIDE_SHOT_BEARING + progress * 360,
  };
}

function revealScene(progress) {
  // 3-beat reveal: very-wide → mid → close. Bearing keeps orbiting.
  const c = shotMeta.center;
  const keyframes = [
    { t: 0.00, center: c, zoom: shotMeta.farZoom - 2.6, pitch: 18, bearing: WIDE_SHOT_BEARING },
    { t: 0.40, center: c, zoom: shotMeta.farZoom - 0.6, pitch: 48, bearing: 10 },
    { t: 0.78, center: c, zoom: shotMeta.closeZoom - 0.1, pitch: 66, bearing: 70 },
    { t: 1.00, center: c, zoom: shotMeta.closeZoom + 0.4, pitch: 74, bearing: 120 },
  ];
  return interpolateKeyframes(keyframes, progress);
}

function flyoverScene(progress) {
  if (routeCoordinates.length < 2) return showcaseScene(progress);
  const segments = routeCoordinates.length - 1;
  // Global easing so the drone slows at start/end of the route.
  const eased = easeInOutQuint(progress);
  const scaled = eased * segments;
  const segIdx = Math.min(Math.floor(scaled), segments - 1);
  const local = scaled - segIdx;
  const a = routeCoordinates[segIdx];
  const b = routeCoordinates[segIdx + 1];
  const center = lerpLngLat(a, b, local);
  // Smooth bearing — look ahead toward the next segment for anticipation.
  const headingNow = headingFromTo(a, b);
  const nextIdx = Math.min(segIdx + 1, segments - 1);
  const c2 = routeCoordinates[nextIdx];
  const d2 = routeCoordinates[nextIdx + 1] || c2;
  const headingNext = headingFromTo(c2, d2);
  const bearing = lerp(headingNow, headingNext, easeInOutCubic(local));
  // Subtle altitude/pitch breath along the path.
  const zoom = shotMeta.closeZoom - 0.5 + 0.2 * Math.sin(progress * Math.PI);
  const pitch = 58 + Math.sin(progress * Math.PI) * 12;
  return { center, zoom, pitch, bearing };
}

function topDownScene(progress) {
  // Slow descent from near-zenith to a gentle 30° tilt, continuously orbiting.
  const eased = easeInOutQuint(progress);
  return {
    center: shotMeta.center,
    zoom: lerp(shotMeta.farZoom + 0.5, shotMeta.closeZoom - 0.2, eased),
    pitch: lerp(2, 30, eased),
    bearing: WIDE_SHOT_BEARING + progress * 180,
  };
}

function applyScene(scene) {
  if (!map) return;
  map.jumpTo({
    center: scene.center,
    zoom: scene.zoom,
    pitch: scene.pitch,
    bearing: scene.bearing,
  });
  if (scene.polygonOpacity !== undefined && map.getLayer("uploaded-fill-extrude")) {
    map.setPaintProperty(
      "uploaded-fill-extrude",
      "fill-extrusion-opacity",
      scene.polygonOpacity,
    );
  }
  updateHud(scene);
}

function resetVisualState() {
  if (fadeEl) fadeEl.style.opacity = "0";
  if (map && map.getLayer("uploaded-fill-extrude")) {
    map.setPaintProperty(
      "uploaded-fill-extrude",
      "fill-extrusion-opacity",
      DEFAULT_POLYGON_OPACITY,
    );
  }
}

function pad(n, len = 2) { return String(Math.abs(n)).padStart(len, "0"); }

function formatDegrees(value, posDir, negDir) {
  const dir = value >= 0 ? posDir : negDir;
  return `${Math.abs(value).toFixed(5)}°${dir}`;
}

function formatTimecode(elapsedMs) {
  const totalFrameCount = Math.floor((elapsedMs / 1000) * fps);
  const f = totalFrameCount % fps;
  const s = Math.floor(totalFrameCount / fps) % 60;
  const m = Math.floor(totalFrameCount / (fps * 60)) % 60;
  const h = Math.floor(totalFrameCount / (fps * 60 * 60));
  return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function updateHud(scene) {
  if (hudLatEl) hudLatEl.textContent = formatDegrees(scene.center[1], "N", "S");
  if (hudLonEl) hudLonEl.textContent = formatDegrees(scene.center[0], "E", "W");
  const bearing = ((scene.bearing % 360) + 360) % 360;
  if (hudBrgEl) hudBrgEl.textContent = `${pad(Math.round(bearing), 3)}°`;
  if (hudPchEl) hudPchEl.textContent = `${pad(Math.round(scene.pitch))}°`;
  if (hudZoomEl) hudZoomEl.textContent = scene.zoom.toFixed(2);
  if (compassNeedleEl) {
    compassNeedleEl.style.transform = `rotate(${-bearing}deg)`;
  }
}

function togglePreview() {
  if (!geojsonLoaded || !map) return;
  if (isRecording) return; // recording owns the animation; don't fight it
  if (cinematicAnimationFrame) {
    cancelPreview();
    return;
  }
  playCinematicRoute();
}

function cancelPreview() {
  if (cinematicAnimationFrame) {
    cancelAnimationFrame(cinematicAnimationFrame);
    cinematicAnimationFrame = null;
  }
  resetVisualState();
  routeProgress = 0;
  updateRouteProgressLayer();
  if (routeStatusEl) routeStatusEl.textContent = "preview stopped";
  if (hudStateEl) hudStateEl.textContent = geojsonLoaded ? "READY" : "STANDBY";
  if (hudRecLabelEl) hudRecLabelEl.textContent = "STANDBY";
  setPreviewButtonState(false);
}

function setPreviewButtonState(playing) {
  if (!previewRouteBtn) return;
  previewRouteBtn.classList.toggle("is-playing", playing);
  const label = previewRouteBtn.querySelector(".mono");
  // First child span carries the play glyph + label; rewrite both.
  if (playing) {
    previewRouteBtn.innerHTML = `<span class="mono">■</span> Stop`;
  } else {
    previewRouteBtn.innerHTML = `<span class="mono">▶</span> Preview`;
  }
}

function playCinematicRoute() {
  if (!geojsonLoaded || !map) return;
  if (cinematicAnimationFrame) {
    cancelAnimationFrame(cinematicAnimationFrame);
    cinematicAnimationFrame = null;
  }

  resetVisualState();
  routeProgress = 0;
  updateRouteProgressLayer();
  if (routeStatusEl) routeStatusEl.textContent = isRecording ? "rolling" : "preview rolling";
  if (hudStateEl) hudStateEl.textContent = isRecording ? "RECORDING" : "PREVIEW";
  if (hudRecLabelEl) hudRecLabelEl.textContent = isRecording ? "REC" : "PREVIEW";
  if (!isRecording) setPreviewButtonState(true);

  const start = performance.now();

  const tick = (now) => {
    const elapsed = Math.min(now - start, cinematicDuration);
    routeProgress = elapsed / cinematicDuration;
    const scene = getCinematicScene(routeProgress);
    applyScene(scene);
    updateRouteProgressLayer();
    if (hudTcEl) hudTcEl.textContent = formatTimecode(elapsed);
    if (hudFrameEl) {
      const frame = Math.min(Math.floor((elapsed / 1000) * fps), totalFrames);
      hudFrameEl.textContent = `${pad(frame, 4)} / ${totalFrames}`;
    }

    // Fade-to-black between scenes comes from the scene itself (v2 logic).
    const fadeOpacity = scene.fade ?? 0;
    if (fadeEl) fadeEl.style.opacity = String(fadeOpacity);
    if (isRecording) {
      drawRecordFrame({ opacity: fadeOpacity, color: "rgba(0, 0, 0, 1)" });
    }

    if (routeProgress < 1) {
      cinematicAnimationFrame = requestAnimationFrame(tick);
    } else {
      cinematicAnimationFrame = null;
      resetVisualState();
      if (routeStatusEl) routeStatusEl.textContent = isRecording ? "rendering" : "done";
      if (hudStateEl && !isRecording) hudStateEl.textContent = "DONE";
      if (!isRecording) setPreviewButtonState(false);
    }
  };

  cinematicAnimationFrame = requestAnimationFrame(tick);
}

function pickRecordingMimeType() {
  const candidates = [
    "video/mp4;codecs=avc1.42E01F,mp4a.40.2",
    "video/mp4;codecs=avc1,mp4a",
    "video/mp4;codecs=avc1",
    "video/mp4",
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
  ];

  for (const mime of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return "video/webm";
}

function extensionForMime(mime) {
  return (mime || "").toLowerCase().includes("mp4") ? "mp4" : "webm";
}

function codecTagForMime(mime) {
  const lc = (mime || "").toLowerCase();
  if (lc.includes("mp4")) return "MP4 · H.264";
  if (lc.includes("vp9")) return "WebM · VP9";
  if (lc.includes("vp8")) return "WebM · VP8";
  return "WebM";
}

async function recordCinematicRoute(options = {}) {
  const shouldDownload = options.download !== false;
  if (!geojsonLoaded || !map || isRecording) return null;
  const canvas = map.getCanvas();
  if (!canvas || typeof canvas.captureStream !== "function" || typeof MediaRecorder === "undefined") {
    setStatus("MediaRecorder not supported in this browser.", true);
    return null;
  }

  let resultBlob = null;
  let resultMime = null;
  try {
    applyScene(getCinematicScene(0));
    await waitForMapIdle();
    await waitForNextFrame();

    // prime the record canvas with the first frame so captureStream has data
    syncRecordCanvasSize();
    drawRecordFrame({ opacity: 0, color: "rgba(0,0,0,0)" });

    recordedChunks = [];
    const stream = recordCanvas.captureStream(fps);
    const mimeType = pickRecordingMimeType();
    resultMime = mimeType;
    mediaRecorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 12_000_000,
    });

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) recordedChunks.push(event.data);
    };

    const finished = new Promise((resolve) => {
      mediaRecorder.onstop = () => resolve();
    });

    isRecording = true;
    mapWrapEl.classList.add("is-recording");
    recordRouteBtn.classList.add("is-armed");
    recordRouteBtn.disabled = true;
    previewRouteBtn.disabled = true;
    setPreviewButtonState(false);
    formatBtns.forEach((btn) => { btn.disabled = true; });
    presetBtns.forEach((btn) => { btn.disabled = true; });
    const labelEl = recordRouteBtn.querySelector(".btn-record-label");
    if (labelEl) labelEl.textContent = "Recording…";

    mediaRecorder.start();
    playCinematicRoute();

    window.setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    }, cinematicDuration + 400);

    await finished;

    if (recordedChunks.length) {
      resultBlob = new Blob(recordedChunks, { type: resultMime });
      if (shouldDownload) triggerDownload(resultBlob);
      const durSec = Math.round(cinematicDuration / 1000);
      setStatus(`${durSec}s cinematic capture downloaded (${codecTagForMime(resultMime)}).`);
    } else {
      setStatus("recording came back empty.", true);
    }
  } catch (error) {
    setStatus(`Recording failed: ${error.message}`, true);
  } finally {
    isRecording = false;
    mapWrapEl.classList.remove("is-recording");
    recordRouteBtn.classList.remove("is-armed");
    const labelEl = recordRouteBtn.querySelector(".btn-record-label");
    if (labelEl) labelEl.textContent = "Record";
    recordRouteBtn.disabled = !geojsonLoaded;
    previewRouteBtn.disabled = !geojsonLoaded;
    formatBtns.forEach((btn) => { btn.disabled = false; });
    presetBtns.forEach((btn) => { btn.disabled = false; });
    if (hudStateEl) hudStateEl.textContent = geojsonLoaded ? "READY" : "STANDBY";
    if (hudRecLabelEl) hudRecLabelEl.textContent = "STANDBY";
  }
  return resultBlob;
}

function waitForNextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function waitForMapIdle() {
  return new Promise((resolve) => {
    if (map.loaded() && !map.isMoving() && !map.isZooming() && !map.isRotating()) {
      resolve();
      return;
    }
    map.once("idle", () => resolve());
  });
}

function triggerDownload(blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const ext = extensionForMime(blob && blob.type);
  link.href = url;
  link.download = `celebi-plug-${activePreset}-${timestamp}.${ext}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

function getDistanceMeters(start, end) {
  const earthRadiusMeters = 6371000;
  const startLat = toRadians(start[1]);
  const endLat = toRadians(end[1]);
  const latDiff = toRadians(end[1] - start[1]);
  const lngDiff = toRadians(end[0] - start[0]);
  const haversine =
    Math.sin(latDiff / 2) * Math.sin(latDiff / 2) +
    Math.cos(startLat) * Math.cos(endLat) * Math.sin(lngDiff / 2) * Math.sin(lngDiff / 2);
  return earthRadiusMeters * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function toRadians(value) { return (value * Math.PI) / 180; }

// ============================================================
// Agent autopilot — URL params + window.celebiPlug API.
//
// Two ways to drive the studio from outside the UI:
//   1. Deep-link URL:
//        /?lat=41.0082&lon=28.9784&radius=80
//          &preset=orbit&aspect=16-9&autostart=1
//      Token must already be in localStorage (set once via the welcome
//      screen) — URL never carries the Mapbox token.
//   2. JS bridge for browser-automation agents:
//        await window.celebiPlug.loadCoordinates([28.9784, 41.0082])
//        window.celebiPlug.setPreset("orbit")
//        const blob = await window.celebiPlug.record()
// ============================================================

function selectPreset(name) {
  if (!presetLabels[name]) return false;
  activePreset = name;
  presetBtns.forEach((btn) => btn.classList.toggle("active", btn.dataset.preset === name));
  updateCanvasLayout();
  resetVisualState();
  return true;
}

function selectAspect(name) {
  if (!aspectLabels[name]) return false;
  activeAspect = name;
  formatBtns.forEach((btn) => btn.classList.toggle("active", btn.dataset.aspect === name));
  updateCanvasLayout();
  return true;
}

async function maybeRunAutopilot() {
  const params = new URLSearchParams(window.location.search);
  if (![...params.keys()].length) return;

  const preset = params.get("preset");
  if (preset) selectPreset(preset);

  const aspect = params.get("aspect");
  if (aspect) selectAspect(aspect);

  const radiusParam = params.get("radius");
  const explicitRadius = radiusParam !== null ? parseFloat(radiusParam) : NaN;

  const lat = parseFloat(params.get("lat"));
  const lon = parseFloat(params.get("lon"));
  const q = params.get("q");

  // Coordinate wins when both supplied — explicit beats inferred.
  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    const r = Number.isFinite(explicitRadius) ? explicitRadius : 60;
    try {
      await loadGeoJsonObject(
        makeSquareGeoJson([lon, lat], r),
        `pin ${lon.toFixed(5)}, ${lat.toFixed(5)}`,
      );
    } catch (_e) {
      return;
    }
  } else if (q) {
    // Geocode the place name via the same path Search uses. When the
    // agent omits radius, auto-tune from the geocoder's place_type so a
    // door-number query frames the building and a city query frames
    // the district.
    if (searchInputEl) searchInputEl.value = q;
    if (Number.isFinite(explicitRadius) && searchRadiusInput) {
      searchRadiusInput.value = String(explicitRadius);
    }
    selectSourceTab("search");
    const feat = await runSearch(q, { autoTune: !Number.isFinite(explicitRadius) });
    if (!feat) return;
  }

  // POI selection — agent can opt in/out before recording rolls.
  //   poi=skip          → don't auto-select any POI (cinematic uses
  //                       synthetic offset targets instead)
  //   poi=auto          → auto-select the 2 closest POIs
  //   poi=auto:N        → auto-select the N closest POIs (capped at 2)
  //   poi=names:A,B     → select POIs whose name contains A or B
  const poiParam = params.get("poi");
  if (poiParam && geojsonLoaded) {
    if (poiParam === "skip") {
      applyPoiSelection([]);
      setShowcaseSkipPoiScenes(true);
    } else if (poiParam.startsWith("auto")) {
      const n = parseInt(poiParam.split(":")[1] || "2", 10) || 2;
      autoPickPois(n);
      setShowcaseSkipPoiScenes(false);
    } else if (poiParam.startsWith("names:")) {
      const names = poiParam.slice("names:".length).split(",").map((s) => s.trim()).filter(Boolean);
      pickPoisByNames(names);
      setShowcaseSkipPoiScenes(false);
    }
  }

  if (params.get("autostart") === "1" && geojsonLoaded) {
    // give Mapbox a beat to load tiles for the new center
    await new Promise((r) => window.setTimeout(r, 1500));
    await waitForMapIdle();
    await recordCinematicRoute();
  }
}

// Programmatic POI selection — shared by URL autopilot and the
// celebiPlug JS bridge. Mirrors what the click handler in
// renderNearbyPois does, so visual state stays in sync.
function applyPoiSelection(indexes) {
  const valid = indexes
    .filter((i) => Number.isInteger(i) && i >= 0 && i < nearbyPois.length)
    .slice(0, 2); // showcase preset uses at most 2 POIs
  selectedPoiIndexes = valid;
  shotMeta.pois = getSelectedPois();
  renderPoiMarkers(shotMeta.pois);
  renderNearbyPois(nearbyPois, nearbyStatusEl?.textContent || "");
  if (activeShotLabelEl) {
    activeShotLabelEl.textContent = computeShotLabel().toUpperCase();
  }
}

function autoPickPois(n = 2) {
  const count = Math.min(Math.max(n, 0), 2);
  applyPoiSelection(Array.from({ length: count }, (_, i) => i));
}

function pickPoisByNames(names) {
  if (!Array.isArray(names) || !names.length) return;
  const lc = names.map((s) => s.toLocaleLowerCase("tr-TR"));
  const matches = [];
  nearbyPois.forEach((poi, idx) => {
    if (matches.length >= 2) return;
    const name = (poi.name || "").toLocaleLowerCase("tr-TR");
    if (lc.some((needle) => name.includes(needle))) matches.push(idx);
  });
  applyPoiSelection(matches);
}

function exposeAgentApi() {
  window.celebiPlug = {
    isReady: () => Boolean(map) && geojsonLoaded,
    hasMap: () => Boolean(map),
    getState: () => ({
      hasMap: Boolean(map),
      geojsonLoaded,
      isRecording,
      activePreset,
      activeAspect,
      center: shotMeta.center,
      pois: shotMeta.pois.map((p) => ({ name: p.name, coordinates: p.coordinates })),
    }),
    loadCoordinates: (lonLat, radiusMeters = 50) =>
      loadGeoJsonObject(
        makeSquareGeoJson(lonLat, radiusMeters),
        `pin ${lonLat[0].toFixed(5)}, ${lonLat[1].toFixed(5)}`,
      ),
    loadGeoJson: (geojson, label = "external geojson") =>
      loadGeoJsonObject(geojson, label),
    search: (query, options) => runSearch(query, options || {}),
    loadBbox: ([west, south, east, north]) =>
      buildAndLoadBbox(west, south, east, north),
    getPois: () => nearbyPois.map((p, i) => ({
      index: i,
      name: p.name,
      coordinates: p.coordinates,
      distanceMeters: p.distanceMeters,
      selected: selectedPoiIndexes.includes(i),
    })),
    selectPois: (indexes) => applyPoiSelection(indexes),
    autoPickPois: (n) => autoPickPois(n),
    pickPoisByNames: (names) => pickPoisByNames(names),
    clearPois: () => applyPoiSelection([]),
    setSkipPoiScenes: (flag) => setShowcaseSkipPoiScenes(flag),
    setPreset: selectPreset,
    setAspect: selectAspect,
    selectSourceTab,
    armPinPick,
    disarmPinPick,
    armBboxDraw,
    disarmBboxDraw,
    preview: () => {
      if (!geojsonLoaded) throw new Error("no source loaded");
      playCinematicRoute();
      return new Promise((resolve) =>
        window.setTimeout(resolve, cinematicDuration + 200),
      );
    },
    stopPreview: cancelPreview,
    record: (options = {}) => recordCinematicRoute(options),
  };
}

// ============================================================
// Source modes — tab switching, geocoder search, on-map pin.
// All three flow into loadGeoJsonObject so downstream code
// (POI scan, route extraction, presets, recording) is identical
// no matter how the target was chosen.
// ============================================================

function selectSourceTab(mode) {
  const valid = ["upload", "search", "pin", "box"];
  if (!valid.includes(mode)) return false;
  sourceTabBtns.forEach((btn) => btn.classList.toggle("is-active", btn.dataset.sourceTab === mode));
  sourcePaneEls.forEach((pane) => pane.classList.toggle("hidden", pane.dataset.sourcePane !== mode));
  // Auto-arm the matching map-interaction when entering pin/box tabs, and
  // tear it down when leaving — saves the user the extra click.
  if (mode === "pin") armPinPick();
  else disarmPinPick();
  if (mode === "box") armBboxDraw();
  else disarmBboxDraw();
  return true;
}

function setSourceStatus(el, text, kind) {
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("is-success", kind === "success");
  el.classList.toggle("is-error", kind === "error");
}

function getSearchRadius() {
  const raw = parseFloat(searchRadiusInput?.value);
  if (!Number.isFinite(raw) || raw <= 0) return 60;
  return Math.min(Math.max(raw, 10), 2000);
}

// Pick a sane default radius from the geocoder's place_type. The more
// specific the result (address > neighborhood > city), the tighter the
// shot — so a door-number query frames the building, while a city query
// frames the district.
function pickRadiusFromPlaceType(placeTypes) {
  const types = Array.isArray(placeTypes) ? placeTypes : [];
  if (types.includes("address")) return 30;
  if (types.includes("poi")) return 40;
  if (types.includes("neighborhood")) return 100;
  if (types.includes("postcode")) return 120;
  if (types.includes("locality")) return 250;
  if (types.includes("place")) return 600;
  return 200;
}

async function runSearch(rawQuery, options = {}) {
  const query = (rawQuery || "").trim();
  if (!query) return null;
  if (!map) {
    setSourceStatus(searchStatusEl, "studio not ready", "error");
    return null;
  }
  const token = mapboxgl.accessToken;
  if (!token) {
    setSourceStatus(searchStatusEl, "missing token", "error");
    return null;
  }
  setSourceStatus(searchStatusEl, "geocoding…");
  try {
    const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(query)}.json?access_token=${encodeURIComponent(token)}&limit=1`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const feat = data.features?.[0];
    if (!feat) {
      setSourceStatus(searchStatusEl, "no match", "error");
      return null;
    }
    const [lon, lat] = feat.center;
    const placeName = feat.place_name || feat.text || `${lon.toFixed(5)}, ${lat.toFixed(5)}`;
    let radius;
    if (options.autoTune === true) {
      radius = pickRadiusFromPlaceType(feat.place_type);
      if (searchRadiusInput) searchRadiusInput.value = String(radius);
    } else {
      radius = getSearchRadius();
    }
    const geojson = bboxOrSquareGeoJson(feat.bbox, [lon, lat], radius, placeName);
    await loadGeoJsonObject(geojson, placeName);
    const typeTag = (feat.place_type || ["?"])[0];
    setSourceStatus(searchStatusEl, `→ ${placeName} · ${typeTag} · R=${radius}m`, "success");
    return feat;
  } catch (error) {
    setSourceStatus(searchStatusEl, `failed: ${error.message}`, "error");
    return null;
  }
}

// Use the geocoder's bbox only when it's already small enough that the
// user's R-meter square would be tighter. For anything bigger (a district,
// city, country), trust the user's radius input and ignore the bbox.
function bboxOrSquareGeoJson(bbox, lonLat, radiusMeters, placeName) {
  if (Array.isArray(bbox) && bbox.length === 4 && bbox.every(Number.isFinite)) {
    const [w, s, e, n] = bbox;
    const centerLat = lonLat[1];
    const mPerDegLat = 111320;
    const mPerDegLng = 111320 * Math.cos((centerLat * Math.PI) / 180);
    const widthM = Math.abs(e - w) * Math.max(mPerDegLng, 1);
    const heightM = Math.abs(n - s) * mPerDegLat;
    const longestSideM = Math.max(widthM, heightM);
    // bbox wins only when it's tighter than the user's R square would be
    if (longestSideM > 0 && longestSideM < radiusMeters * 2) {
      return {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: { celebiPlugSearch: true, place: placeName },
            geometry: {
              type: "Polygon",
              coordinates: [[
                [w, s], [e, s], [e, n], [w, n], [w, s],
              ]],
            },
          },
        ],
      };
    }
  }
  const gj = makeSquareGeoJson(lonLat, radiusMeters);
  gj.features[0].properties.place = placeName;
  return gj;
}

function parsePinCoords(text) {
  if (!text) return null;
  const parts = text
    .trim()
    .replace(/[°nesw]/gi, "")
    .split(/[,;\s]+/)
    .map((v) => parseFloat(v))
    .filter((v) => Number.isFinite(v));
  if (parts.length < 2) return null;
  const lat = parts[0];
  const lon = parts[1];
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon, radius: Number.isFinite(parts[2]) ? parts[2] : null };
}

function getPinRadius() {
  const raw = parseFloat(pinRadiusInput?.value);
  if (!Number.isFinite(raw) || raw <= 0) return 80;
  return Math.min(Math.max(raw, 10), 2000);
}

async function runPinFromInput() {
  const parsed = parsePinCoords(pinCoordsInput.value);
  if (!parsed) {
    setSourceStatus(pinStatusEl, "expected: lat, lon", "error");
    return null;
  }
  const radius = Number.isFinite(parsed.radius) ? parsed.radius : getPinRadius();
  return runPinAt(parsed.lat, parsed.lon, radius);
}

async function runPinAt(lat, lon, radius) {
  if (!map) {
    setSourceStatus(pinStatusEl, "studio not ready", "error");
    return null;
  }
  setSourceStatus(pinStatusEl, "dropping pin…");
  try {
    const label = `pin ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
    await loadGeoJsonObject(makeSquareGeoJson([lon, lat], radius), label);
    pinCoordsInput.value = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
    placePinMarker([lon, lat]);
    setSourceStatus(pinStatusEl, `→ ${label} · R=${radius}m`, "success");
    return { lat, lon, radius };
  } catch (error) {
    setSourceStatus(pinStatusEl, `failed: ${error.message}`, "error");
    return null;
  }
}

let pinMarker = null;

function placePinMarker(lngLat) {
  if (!map) return;
  if (pinMarker) {
    pinMarker.setLngLat(lngLat);
    return;
  }
  const el = document.createElement("div");
  el.className = "pin-marker";
  pinMarker = new mapboxgl.Marker({ element: el, draggable: true, anchor: "center" })
    .setLngLat(lngLat)
    .addTo(map);
  pinMarker.on("dragend", () => {
    const { lng, lat } = pinMarker.getLngLat();
    runPinAt(lat, lng, getPinRadius());
  });
}

function clearPinMarker() {
  if (pinMarker) {
    pinMarker.remove();
    pinMarker = null;
  }
}

let pinPickArmed = false;

function installMapPinHandler() {
  if (!map) return;
  map.on("click", (event) => {
    if (!pinPickArmed) return;
    const { lng, lat } = event.lngLat;
    runPinAt(lat, lng, getPinRadius());
    // keep armed → user can re-click to relocate; disarm via tab change or ESC
  });
}

function armPinPick() {
  if (!map) return;
  pinPickArmed = true;
  if (pinPickMapBtn) {
    pinPickMapBtn.classList.add("is-armed");
    pinPickMapBtn.textContent = "Click map ▼";
  }
  const canvas = map.getCanvas();
  if (canvas) canvas.classList.add("is-pin-armed");
  setSourceStatus(pinStatusEl, "click anywhere on map to drop pin");
}

function disarmPinPick() {
  pinPickArmed = false;
  if (pinPickMapBtn) {
    pinPickMapBtn.classList.remove("is-armed");
    pinPickMapBtn.textContent = "Pick on map";
  }
  if (map) {
    const canvas = map.getCanvas();
    if (canvas) canvas.classList.remove("is-pin-armed");
  }
}

// ============================================================
// Bbox drag — user drags a rectangle on the map; we build a
// polygon from the drag corners and route it through the same
// loadGeoJsonObject pipeline as every other input source.
// ============================================================

let boxDrawArmed = false;
let boxDragStartLngLat = null;
let boxDragStartPixel = null;
let boxOverlayEl = null;

function armBboxDraw() {
  if (!map) return;
  boxDrawArmed = true;
  if (boxDrawBtn) {
    boxDrawBtn.classList.add("is-armed");
    boxDrawBtn.textContent = "Drag map ▭";
  }
  const canvas = map.getCanvas();
  if (canvas) canvas.classList.add("is-pin-armed");
  // Disable map pan/box-zoom so our drag handler can claim the gesture.
  map.dragPan.disable();
  if (map.boxZoom) map.boxZoom.disable();
  map.getCanvasContainer().addEventListener("mousedown", onBboxMouseDown);
  setSourceStatus(boxStatusEl, "drag a rectangle on the map");
}

function disarmBboxDraw() {
  boxDrawArmed = false;
  if (boxDrawBtn) {
    boxDrawBtn.classList.remove("is-armed");
    boxDrawBtn.textContent = "Drag on map";
  }
  if (map) {
    const canvas = map.getCanvas();
    if (canvas) canvas.classList.remove("is-pin-armed");
    map.dragPan.enable();
    if (map.boxZoom) map.boxZoom.enable();
    map.getCanvasContainer().removeEventListener("mousedown", onBboxMouseDown);
  }
  document.removeEventListener("mousemove", onBboxMouseMove);
  document.removeEventListener("mouseup", onBboxMouseUp);
  cleanupBboxOverlay();
  boxDragStartLngLat = null;
  boxDragStartPixel = null;
}

function cleanupBboxOverlay() {
  if (boxOverlayEl) {
    boxOverlayEl.remove();
    boxOverlayEl = null;
  }
}

function onBboxMouseDown(event) {
  if (!boxDrawArmed || event.button !== 0) return;
  event.preventDefault();
  event.stopPropagation();
  const rect = map.getCanvas().getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  boxDragStartLngLat = map.unproject([x, y]);
  boxDragStartPixel = { x, y };
  cleanupBboxOverlay();
  boxOverlayEl = document.createElement("div");
  boxOverlayEl.className = "bbox-drag-overlay";
  boxOverlayEl.style.left = `${x}px`;
  boxOverlayEl.style.top = `${y}px`;
  boxOverlayEl.style.width = "0px";
  boxOverlayEl.style.height = "0px";
  mapWrapEl.appendChild(boxOverlayEl);
  document.addEventListener("mousemove", onBboxMouseMove);
  document.addEventListener("mouseup", onBboxMouseUp);
}

function onBboxMouseMove(event) {
  if (!boxDragStartPixel || !boxOverlayEl) return;
  const rect = map.getCanvas().getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const sx = boxDragStartPixel.x;
  const sy = boxDragStartPixel.y;
  boxOverlayEl.style.left = `${Math.min(sx, x)}px`;
  boxOverlayEl.style.top = `${Math.min(sy, y)}px`;
  boxOverlayEl.style.width = `${Math.abs(x - sx)}px`;
  boxOverlayEl.style.height = `${Math.abs(y - sy)}px`;
}

function onBboxMouseUp(event) {
  if (!boxDragStartLngLat || !boxDragStartPixel) return;
  document.removeEventListener("mousemove", onBboxMouseMove);
  document.removeEventListener("mouseup", onBboxMouseUp);
  const rect = map.getCanvas().getBoundingClientRect();
  const endX = event.clientX - rect.left;
  const endY = event.clientY - rect.top;
  const dragPx = Math.hypot(endX - boxDragStartPixel.x, endY - boxDragStartPixel.y);
  cleanupBboxOverlay();
  const endLngLat = map.unproject([endX, endY]);
  const start = boxDragStartLngLat;
  boxDragStartLngLat = null;
  boxDragStartPixel = null;
  if (dragPx < 14) {
    setSourceStatus(boxStatusEl, "drag farther — box too small", "error");
    return;
  }
  const west = Math.min(start.lng, endLngLat.lng);
  const east = Math.max(start.lng, endLngLat.lng);
  const south = Math.min(start.lat, endLngLat.lat);
  const north = Math.max(start.lat, endLngLat.lat);
  buildAndLoadBbox(west, south, east, north);
}

async function buildAndLoadBbox(west, south, east, north) {
  setSourceStatus(boxStatusEl, "loading bbox…");
  try {
    const geojson = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { celebiPlugBox: true },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [west, south], [east, south], [east, north], [west, north], [west, south],
            ]],
          },
        },
      ],
    };
    const label = `bbox ${west.toFixed(4)}, ${south.toFixed(4)} → ${east.toFixed(4)}, ${north.toFixed(4)}`;
    await loadGeoJsonObject(geojson, label);
    setSourceStatus(boxStatusEl, `→ ${label}`, "success");
  } catch (error) {
    setSourceStatus(boxStatusEl, `failed: ${error.message}`, "error");
  }
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (pinPickArmed) disarmPinPick();
  if (boxDrawArmed) disarmBboxDraw();
  if (resultModalEl && !resultModalEl.classList.contains("hidden")) closeResultModal();
});

// ============================================================
// Result modal — preview the just-recorded clip + re-record
// without losing setup.
// ============================================================

let currentRecordingBlob = null;
let currentRecordingObjectUrl = null;

async function uiRecord() {
  const blob = await recordCinematicRoute({ download: false });
  if (blob) showResultModal(blob);
}

function showResultModal(blob) {
  if (!resultModalEl || !resultVideoEl) return;
  if (currentRecordingObjectUrl) URL.revokeObjectURL(currentRecordingObjectUrl);
  currentRecordingBlob = blob;
  currentRecordingObjectUrl = URL.createObjectURL(blob);
  resultVideoEl.src = currentRecordingObjectUrl;
  resultVideoEl.load();
  // Autoplay may be rejected by the browser if the page hasn't been
  // interacted with — swallow that, the user can press play.
  resultVideoEl.play().catch(() => {});
  if (resultMetaEl) {
    const sizeMB = (blob.size / 1_000_000).toFixed(1);
    const durSec = Math.round(cinematicDuration / 1000);
    const tag = showcaseSkipPoiScenes ? "sparse" : (selectedPoiIndexes.length ? "with POI" : "default");
    const codec = codecTagForMime(blob.type);
    resultMetaEl.textContent = `${(presetLabels[activePreset] || activePreset).toUpperCase()} · ${aspectLabels[activeAspect] || activeAspect} · ${durSec}s · ${tag} · ${sizeMB} MB · ${codec}`;
  }
  resultModalEl.classList.remove("hidden");
}

function closeResultModal() {
  if (!resultModalEl) return;
  resultModalEl.classList.add("hidden");
  if (resultVideoEl) {
    resultVideoEl.pause();
    resultVideoEl.removeAttribute("src");
    resultVideoEl.load();
  }
  if (currentRecordingObjectUrl) {
    URL.revokeObjectURL(currentRecordingObjectUrl);
    currentRecordingObjectUrl = null;
  }
  currentRecordingBlob = null;
}

function bindResultModal() {
  if (!resultModalEl) return;
  resultModalEl.addEventListener("click", (event) => {
    if (event.target.dataset.closeResult !== undefined) closeResultModal();
  });
  if (closeResultBtn) closeResultBtn.addEventListener("click", closeResultModal);
  if (resultDownloadBtn) {
    resultDownloadBtn.addEventListener("click", () => {
      if (currentRecordingBlob) triggerDownload(currentRecordingBlob);
    });
  }
  if (resultRerecordWithPoiBtn) {
    resultRerecordWithPoiBtn.addEventListener("click", () => {
      // Force POI mode on: auto-pick top 2 if none selected, disable
      // skip-POI 3-scene mode if it was active. Then re-record.
      if (!selectedPoiIndexes.length) autoPickPois(2);
      setShowcaseSkipPoiScenes(false);
      closeResultModal();
      uiRecord();
    });
  }
  if (resultRerecordNoPoiBtn) {
    resultRerecordNoPoiBtn.addEventListener("click", () => {
      // Clear any POI selection and engage the sparse 3-scene 36s pilot.
      applyPoiSelection([]);
      setShowcaseSkipPoiScenes(true);
      closeResultModal();
      uiRecord();
    });
  }
}

// ============================================================
// Polygon corner handles — drag a corner of a synthetic square
// to resize the framing. Maintains the rectangle (opposite corner
// stays fixed, two adjacent corners follow the dragged one).
// ============================================================

let polygonHandleMarkers = [];
let currentSyntheticBounds = null;

function placePolygonHandles(bounds) {
  if (!map) return;
  clearPolygonHandles();
  const corners = ["sw", "se", "ne", "nw"];
  corners.forEach((cornerId) => {
    const el = document.createElement("div");
    el.className = `polygon-handle polygon-handle-${cornerId}`;
    el.title = "Drag to resize";
    const lngLat = cornerLngLat(cornerId, bounds);
    const marker = new mapboxgl.Marker({ element: el, draggable: true, anchor: "center" })
      .setLngLat(lngLat)
      .addTo(map);
    marker.on("drag", () => {
      if (!currentSyntheticBounds) return;
      const ll = marker.getLngLat();
      const newBounds = boundsFromHandleDrag(cornerId, ll.lng, ll.lat, currentSyntheticBounds);
      currentSyntheticBounds = newBounds;
      updatePolygonSource(newBounds);
      repositionOtherHandles(cornerId, newBounds);
    });
    marker.on("dragend", () => {
      if (!currentSyntheticBounds) return;
      finalizePolygonResize(currentSyntheticBounds);
    });
    polygonHandleMarkers.push({ marker, corner: cornerId });
  });
}

function clearPolygonHandles() {
  polygonHandleMarkers.forEach(({ marker }) => marker.remove());
  polygonHandleMarkers = [];
}

function cornerLngLat(cornerId, b) {
  if (cornerId === "sw") return [b.west, b.south];
  if (cornerId === "se") return [b.east, b.south];
  if (cornerId === "ne") return [b.east, b.north];
  if (cornerId === "nw") return [b.west, b.north];
  return [b.west, b.south];
}

function boundsFromHandleDrag(cornerId, lng, lat, prev) {
  const b = { ...prev };
  if (cornerId === "sw") { b.west = lng; b.south = lat; }
  if (cornerId === "se") { b.east = lng; b.south = lat; }
  if (cornerId === "ne") { b.east = lng; b.north = lat; }
  if (cornerId === "nw") { b.west = lng; b.north = lat; }
  if (b.west > b.east) [b.west, b.east] = [b.east, b.west];
  if (b.south > b.north) [b.south, b.north] = [b.north, b.south];
  return b;
}

function repositionOtherHandles(draggingId, bounds) {
  polygonHandleMarkers.forEach(({ marker, corner }) => {
    if (corner === draggingId) return;
    marker.setLngLat(cornerLngLat(corner, bounds));
  });
}

function synthGeoJsonFromBounds(b) {
  const { west, east, south, north } = b;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { celebiPlugSyntheticPin: true },
        geometry: {
          type: "Polygon",
          coordinates: [[
            [west, south], [east, south], [east, north], [west, north], [west, south],
          ]],
        },
      },
    ],
  };
}

function updatePolygonSource(bounds) {
  if (!map) return;
  const src = map.getSource("uploaded-geojson");
  if (!src) return;
  src.setData(synthGeoJsonFromBounds(bounds));
}

function finalizePolygonResize(bounds) {
  const newGeoJson = synthGeoJsonFromBounds(bounds);
  routeCoordinates = extractRouteCoordinates(newGeoJson);
  shotMeta = calculateShotMeta(newGeoJson, routeCoordinates);
  shotMeta.pois = getSelectedPois(); // keep selected POIs
  routeProgress = 0;
  updateRouteProgressLayer();
  setRouteControls(true, `resized · ${routeCoordinates.length || 4} corners`);
}
