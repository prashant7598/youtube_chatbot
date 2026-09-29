(() => {
  "use strict";

  const ROOT_ID = "youtube-rag-extension-root";
  const POSITION_KEY = "youtubeRagOverlayPosition";
  let currentVideo = getVideoContext();
  let sessionId = createSessionId();
  let loadedVideoId = null;
  let isLoading = false;

  function getVideoContext() {
    const url = new URL(window.location.href);
    const id = url.searchParams.get("v") || (url.pathname.match(/\/(shorts|live|embed)\/([\w-]{11})/) || [])[2];
    const title = document.querySelector("h1.ytd-watch-metadata yt-formatted-string")?.textContent?.trim()
      || document.querySelector('meta[name="title"]')?.content?.trim()
      || document.title.replace(/\s*-\s*YouTube\s*$/, "").trim();
    return id ? { id, title } : null;
  }

  function createSessionId() {
    return window.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function api(path, method, body) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "youtube-rag-api", request: { path, method, body } }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error("The extension could not reach its background service."));
          return;
        }
        if (!response?.ok) {
          reject(new Error(response?.error || "The chatbot backend is unavailable."));
          return;
        }
        resolve(response.data);
      });
    });
  }

  function readBrowserCaptions(videoId) {
    return new Promise((resolve) => {
      const requestId = window.crypto?.randomUUID?.() || `captions-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const script = document.createElement("script");
      const cleanup = () => {
        window.removeEventListener("message", onMessage);
        script.remove();
        window.clearTimeout(timeout);
      };
      const onMessage = (event) => {
        const data = event.data;
        if (
          event.source !== window
          || data?.source !== "youtube-rag-page-bridge"
          || data.requestId !== requestId
          || data.videoId !== videoId
        ) return;
        cleanup();
        resolve(data.ok && Array.isArray(data.segments) ? { language: data.language, segments: data.segments } : null);
      };
      const timeout = window.setTimeout(() => {
        cleanup();
        resolve(null);
      }, 8000);
      window.addEventListener("message", onMessage);
      script.src = chrome.runtime.getURL("page-bridge.js");
      script.dataset.requestId = requestId;
      script.dataset.videoId = videoId;
      script.onerror = () => {
        cleanup();
        resolve(null);
      };
      (document.head || document.documentElement).append(script);
    });
  }

  async function mount() {
    if (document.getElementById(ROOT_ID)) return;
    const host = document.createElement("div");
    host.id = ROOT_ID;
    const shadow = host.attachShadow({ mode: "open" });
    try {
      const [markup, styles] = await Promise.all([
        fetch(chrome.runtime.getURL("chat.html")).then((response) => response.text()),
        fetch(chrome.runtime.getURL("chat.css")).then((response) => response.text())
      ]);
      shadow.innerHTML = `<style>${styles}</style>${markup}`;
      document.documentElement.append(host);
      await restorePosition(host);
      wireUi(shadow, host);
    } catch (error) {
      console.error("YouTube Transcript Chat could not mount", error);
      host.remove();
    }
  }

  function wireUi(root, host) {
    const panel = root.getElementById("panel");
    const launcher = root.getElementById("launcher");
    const question = root.getElementById("question");
    const send = root.getElementById("send");
    const messages = root.getElementById("messages");
    const loading = root.getElementById("loading");
    const meta = root.getElementById("video-meta");
    updateMeta(meta);
    isolateKeyboardEvents(host);
    enableDragging(root, host);

    launcher.addEventListener("click", async () => {
      panel.classList.toggle("open");
      if (panel.classList.contains("open")) {
        await ensureLoaded(messages, loading, send);
        question.focus();
      }
    });
    root.getElementById("collapse").addEventListener("click", () => panel.classList.remove("open"));
    root.getElementById("clear").addEventListener("click", async () => {
      messages.replaceChildren();
      if (currentVideo) await api("/api/reset", "POST", { session_id: sessionId, video_id: currentVideo.id }).catch(() => {});
    });
    question.addEventListener("input", () => { question.style.height = "auto"; question.style.height = `${Math.min(question.scrollHeight, 104)}px`; });
    question.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); root.getElementById("composer").requestSubmit(); }
    });
    root.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = question.value.trim();
      if (!text || isLoading) return;
      if (!currentVideo) { addMessage(messages, "error", "Open a YouTube video before asking a question."); return; }
      await ensureLoaded(messages, loading, send);
      if (loadedVideoId !== currentVideo.id) return;
      addMessage(messages, "user", text);
      question.value = ""; question.style.height = "auto";
      setLoading(true, loading, send);
      try {
        const response = await api("/api/chat", "POST", { video_id: currentVideo.id, question: text, session_id: sessionId, video_title: currentVideo.title });
        addMessage(messages, "assistant", response.answer, response.sources || []);
      } catch (error) {
        addMessage(messages, "error", error.message);
      } finally { setLoading(false, loading, send); }
    });
  }

  function isolateKeyboardEvents(host) {
    const stopYouTubeShortcut = (event) => {
      if (event.composedPath().includes(host)) {
        event.stopImmediatePropagation();
      }
    };
    ["keydown", "keyup", "keypress"].forEach((type) => {
      window.addEventListener(type, stopYouTubeShortcut, true);
    });
  }

  function enableDragging(root, host) {
    const handle = root.getElementById("drag-handle");
    let pointerId = null;
    let offsetX = 0;
    let offsetY = 0;

    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("button")) return;
      const bounds = host.getBoundingClientRect();
      pointerId = event.pointerId;
      offsetX = event.clientX - bounds.left;
      offsetY = event.clientY - bounds.top;
      handle.setPointerCapture(pointerId);
      handle.classList.add("dragging");
      event.preventDefault();
      event.stopPropagation();
    });
    handle.addEventListener("pointermove", (event) => {
      if (event.pointerId !== pointerId) return;
      const bounds = host.getBoundingClientRect();
      setPosition(host, event.clientX - offsetX, event.clientY - offsetY, bounds.width, bounds.height);
    });
    handle.addEventListener("pointerup", async (event) => {
      if (event.pointerId !== pointerId) return;
      pointerId = null;
      handle.classList.remove("dragging");
      if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
      await savePosition(host);
    });
    handle.addEventListener("pointercancel", () => {
      pointerId = null;
      handle.classList.remove("dragging");
    });
    window.addEventListener("resize", () => {
      if (!host.style.left) return;
      const bounds = host.getBoundingClientRect();
      setPosition(host, bounds.left, bounds.top, bounds.width, bounds.height);
    });
  }

  function setPosition(host, left, top, width, height) {
    const margin = 8;
    const maxLeft = Math.max(margin, window.innerWidth - width - margin);
    const maxTop = Math.max(margin, window.innerHeight - height - margin);
    host.style.left = `${Math.round(Math.min(Math.max(margin, left), maxLeft))}px`;
    host.style.top = `${Math.round(Math.min(Math.max(margin, top), maxTop))}px`;
    host.style.right = "auto";
    host.style.bottom = "auto";
  }

  async function restorePosition(host) {
    const stored = await chrome.storage.local.get(POSITION_KEY);
    const position = stored[POSITION_KEY];
    if (!position || !Number.isFinite(position.left) || !Number.isFinite(position.top)) return;
    const bounds = host.getBoundingClientRect();
    setPosition(host, position.left, position.top, bounds.width, bounds.height);
  }

  async function savePosition(host) {
    const bounds = host.getBoundingClientRect();
    await chrome.storage.local.set({ [POSITION_KEY]: { left: Math.round(bounds.left), top: Math.round(bounds.top) } });
  }

  async function ensureLoaded(messages, loading, send) {
    if (!currentVideo || loadedVideoId === currentVideo.id || isLoading) return;
    setLoading(true, loading, send, "Indexing transcript");
    try {
      const captions = await readBrowserCaptions(currentVideo.id);
      await api("/api/video/load", "POST", {
        video_id: currentVideo.id,
        title: currentVideo.title,
        ...(captions ? { transcript_language: captions.language, transcript_segments: captions.segments } : {})
      });
      loadedVideoId = currentVideo.id;
    } catch (error) {
      addMessage(messages, "error", error.message);
    } finally { setLoading(false, loading, send); }
  }

  function setLoading(active, loading, send, label = "Working") {
    isLoading = active; loading.textContent = label; loading.classList.toggle("visible", active); send.disabled = active;
  }

  function addMessage(container, kind, text, sources = []) {
    const message = document.createElement("div"); message.className = `message ${kind}`; message.textContent = text;
    if (sources.length) {
      const sourceContainer = document.createElement("div"); sourceContainer.className = "sources";
      sources.forEach((source) => {
        const button = document.createElement("button"); button.type = "button"; button.className = "citation";
        button.textContent = formatTime(source.start_time); button.title = source.text || "Seek to this part of the video";
        button.addEventListener("click", () => seekTo(source.start_time)); sourceContainer.append(button);
      });
      message.append(sourceContainer);
    }
    container.append(message); container.scrollTop = container.scrollHeight;
  }

  function seekTo(seconds) { const player = document.querySelector("video.html5-main-video"); if (player && Number.isFinite(Number(seconds))) { player.currentTime = Number(seconds); player.play().catch(() => {}); } }
  function formatTime(seconds) { const value = Math.max(0, Math.floor(Number(seconds) || 0)); return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`; }
  function updateMeta(element) { element.textContent = currentVideo ? `${currentVideo.title || "Current video"} (${currentVideo.id})` : "No YouTube video detected"; }

  function refreshVideoContext() {
    const nextVideo = getVideoContext();
    if (nextVideo?.id !== currentVideo?.id) {
      currentVideo = nextVideo;
      sessionId = createSessionId();
      loadedVideoId = null;
      const root = document.getElementById(ROOT_ID)?.shadowRoot;
      if (root) root.getElementById("messages").replaceChildren();
    } else if (nextVideo) {
      currentVideo = nextVideo;
    }
    const root = document.getElementById(ROOT_ID)?.shadowRoot;
    if (root) updateMeta(root.getElementById("video-meta"));
  }

  document.addEventListener("yt-navigate-finish", () => window.setTimeout(refreshVideoContext, 150));
  document.addEventListener("yt-page-data-updated", () => window.setTimeout(refreshVideoContext, 150));
  window.addEventListener("popstate", () => window.setTimeout(refreshVideoContext, 150));
  void mount();
})();
