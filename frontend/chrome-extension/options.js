const input = document.getElementById("backend-url");
const status = document.getElementById("status");
chrome.storage.sync.get(["backendUrl"], ({ backendUrl }) => { input.value = backendUrl || "http://127.0.0.1:8000"; });
document.getElementById("save").addEventListener("click", () => {
  const value = input.value.trim().replace(/\/$/, "");
  try { new URL(value); } catch { status.textContent = "Enter a valid URL."; return; }
  chrome.storage.sync.set({ backendUrl: value }, () => { status.textContent = "Saved"; });
});
