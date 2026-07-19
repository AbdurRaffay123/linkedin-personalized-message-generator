// Backend base URL. Override at runtime via chrome.storage (key "apiBase") so the
// same build can point at localhost in dev and a deployed URL in production
// without rebuilding. Keep the host in manifest host_permissions in sync.
export const DEFAULT_API_BASE = "http://localhost:8000/api/v1";

export async function getApiBase(): Promise<string> {
  try {
    const { apiBase } = await chrome.storage.local.get("apiBase");
    return typeof apiBase === "string" && apiBase ? apiBase : DEFAULT_API_BASE;
  } catch {
    return DEFAULT_API_BASE;
  }
}

// API key for the hardened backend. Configured from the popup's Settings panel
// (gear icon) — no console needed. Issue a key with:
//   cd backend && bash start.sh        (prints & saves the key to .devkey.txt)
//   — or —  python -m app.issue_key you@example.com
export async function getApiKey(): Promise<string> {
  try {
    const { apiKey } = await chrome.storage.local.get("apiKey");
    return typeof apiKey === "string" ? apiKey : "";
  } catch {
    return "";
  }
}

/** Persist the backend base URL + API key from the Settings panel. Empty base
 *  falls back to the default; the API key is stored verbatim. */
export async function saveSettings(opts: {
  apiBase: string;
  apiKey: string;
}): Promise<void> {
  await chrome.storage.local.set({
    apiBase: opts.apiBase.trim() || DEFAULT_API_BASE,
    apiKey: opts.apiKey.trim(),
  });
}
