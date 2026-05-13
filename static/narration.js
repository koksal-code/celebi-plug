/**
 * CelebiPlug narration — opt-in audio overlay for the cinematic recorder.
 *
 * Activation: append `?narrate=auto` (auto-generate from /api/narration?q=...)
 * or `?narrate=<text>` to the studio URL. Without the param, this module is
 * dormant and the recording pipeline behaves exactly as before.
 *
 * Wiring (kept minimal in script.js):
 *   1. After place loads:   window.celebiNarration?.prepare(placeName);
 *   2. Before MediaRecorder: const s = await window.celebiNarration?.attach(stream) ?? stream;
 *   3. After recorder stops: window.celebiNarration?.detach();
 */
(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const narrateParam = params.get("narrate");
  if (!narrateParam) return; // dormant — keep studio behaviour unchanged.

  const langParam = (params.get("lang") || "tr").toLowerCase();
  let preparedBlobUrl = null;
  let preparedText = null;
  let audioContext = null;
  let audioElement = null;
  let sourceNode = null;
  let destNode = null;

  async function buildNarrationUrl(place) {
    const qs = new URLSearchParams();
    qs.set("lang", langParam);
    if (narrateParam === "auto") {
      if (!place) return null;
      qs.set("q", place);
      qs.set("auto", "1");
    } else {
      qs.set("text", narrateParam);
    }
    // Pass video duration so the backend calibrates narration length
    const dur = params.get("duration") || window.__celebiDuration;
    if (dur) qs.set("duration", String(dur));
    const resp = await fetch(`/api/narration?${qs}`);
    if (!resp.ok) return null;
    const blob = await resp.blob();
    preparedText = resp.headers.get("X-Celebi-Narration-Text") || null;
    return URL.createObjectURL(blob);
  }

  async function prepare(place) {
    if (preparedBlobUrl) return preparedBlobUrl;
    try {
      preparedBlobUrl = await buildNarrationUrl(place);
    } catch (err) {
      console.warn("celebi narration prepare failed:", err);
      preparedBlobUrl = null;
    }
    return preparedBlobUrl;
  }

  async function attach(videoStream) {
    if (!videoStream) return videoStream;
    if (!preparedBlobUrl) {
      await prepare(window.__celebiCurrentPlace || null);
    }
    if (!preparedBlobUrl) return videoStream; // graceful: silent record stays valid

    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      audioElement = new Audio();
      audioElement.crossOrigin = "anonymous";
      audioElement.preload = "auto";
      audioElement.src = preparedBlobUrl;
      audioElement.loop = false;
      audioElement.muted = false;
      audioElement.volume = 1.0;
      sourceNode = audioContext.createMediaElementSource(audioElement);
      destNode = audioContext.createMediaStreamDestination();
      sourceNode.connect(destNode);
      sourceNode.connect(audioContext.destination); // also play to speakers
      const combined = new MediaStream([
        ...videoStream.getVideoTracks(),
        ...destNode.stream.getAudioTracks(),
      ]);
      // Resume context if it was suspended by autoplay policy.
      if (audioContext.state === "suspended") {
        try { await audioContext.resume(); } catch (_) { /* ignore */ }
      }
      audioElement.currentTime = 0;
      const playPromise = audioElement.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch((err) => console.warn("celebi narration play failed:", err));
      }
      return combined;
    } catch (err) {
      console.warn("celebi narration attach failed:", err);
      detach();
      return videoStream;
    }
  }

  function detach() {
    try {
      if (audioElement) {
        audioElement.pause();
        audioElement.src = "";
      }
    } catch (_) { /* ignore */ }
    try { if (sourceNode) sourceNode.disconnect(); } catch (_) { /* ignore */ }
    try { if (destNode) destNode.disconnect(); } catch (_) { /* ignore */ }
    try { if (audioContext) audioContext.close(); } catch (_) { /* ignore */ }
    audioContext = null;
    audioElement = null;
    sourceNode = null;
    destNode = null;
  }

  function reset() {
    detach();
    if (preparedBlobUrl) {
      try { URL.revokeObjectURL(preparedBlobUrl); } catch (_) { /* ignore */ }
    }
    preparedBlobUrl = null;
    preparedText = null;
  }

  window.celebiNarration = {
    isActive: () => true,
    prepare,
    attach,
    detach,
    reset,
    getText: () => preparedText,
  };
})();
