// Backend base URL. Override at runtime via chrome.storage (key "apiBase") so the
// same build can point at localhost in dev and a deployed URL in production
// without rebuilding. Keep the host in manifest host_permissions in sync.
const DEFAULT_API_BASE = "http://localhost:8000/api/v1";

export async function getApiBase(): Promise<string> {
  try {
    const { apiBase } = await chrome.storage.local.get("apiBase");
    return typeof apiBase === "string" && apiBase ? apiBase : DEFAULT_API_BASE;
  } catch {
    return DEFAULT_API_BASE;
  }
}
