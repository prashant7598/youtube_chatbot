(() => {
  "use strict";

  const script = document.currentScript;
  const requestId = script?.dataset.requestId;
  const videoId = script?.dataset.videoId;

  function reply(payload) {
    window.postMessage({ source: "youtube-rag-page-bridge", requestId, videoId, ...payload }, window.location.origin);
  }

  function playerResponse() {
    if (window.ytInitialPlayerResponse) return window.ytInitialPlayerResponse;
    const serialized = window.ytplayer?.config?.args?.player_response;
    if (!serialized) return null;
    try {
      return JSON.parse(serialized);
    } catch {
      return null;
    }
  }

  function chooseTrack(tracks) {
    return tracks.find((track) => ["hi", "en"].includes(track.languageCode)) || tracks[0];
  }

  async function extractCaptions() {
    const tracks = playerResponse()?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
    const track = chooseTrack(tracks);
    if (!track?.baseUrl) {
      reply({ ok: false, error: "This video does not expose a caption track in YouTube." });
      return;
    }
    const url = new URL(track.baseUrl);
    url.searchParams.set("fmt", "json3");
    const response = await fetch(url.toString(), { credentials: "same-origin" });
    if (!response.ok) throw new Error("YouTube did not return the selected caption track.");
    const payload = await response.json();
    const segments = (payload.events || [])
      .filter((event) => event.segs?.length && Number.isFinite(event.tStartMs))
      .map((event) => ({
        text: event.segs.map((segment) => segment.utf8 || "").join("").replace(/\n/g, " ").trim(),
        start_time: event.tStartMs / 1000,
        duration: (event.dDurationMs || 0) / 1000
      }))
      .filter((segment) => segment.text);
    if (!segments.length) {
      reply({ ok: false, error: "YouTube returned an empty caption track." });
      return;
    }
    reply({ ok: true, language: track.languageCode || "unknown", segments });
  }

  extractCaptions().catch((error) => {
    reply({ ok: false, error: error instanceof Error ? error.message : "Could not read YouTube captions." });
  });
})();
