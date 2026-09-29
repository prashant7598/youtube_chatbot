const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["backendUrl"], ({ backendUrl }) => {
    if (!backendUrl) {
      chrome.storage.sync.set({ backendUrl: DEFAULT_BACKEND_URL });
    }
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "youtube-rag-api") {
    return undefined;
  }
  requestBackend(message.request)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});

async function requestBackend({ path, method = "GET", body }) {
  const { backendUrl = DEFAULT_BACKEND_URL } = await chrome.storage.sync.get(["backendUrl"]);
  const url = `${backendUrl.replace(/\/$/, "")}${path}`;
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(`Cannot reach the chatbot backend at ${backendUrl}. Start it, then reload this YouTube tab.`);
    }
    throw error;
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || "The chatbot backend did not respond correctly.");
  }
  return payload;
}
