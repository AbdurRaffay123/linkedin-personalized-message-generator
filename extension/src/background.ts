// MV3 service worker. Intentionally minimal: the popup orchestrates capture and
// analysis directly. Kept as an extension point for future lifecycle work
// (badges, context menus, notifications) — never for auto-navigation/scraping.

chrome.runtime.onInstalled.addListener(() => {
  console.log("[AI Sales Assistant] installed — passive, user-triggered capture only.");
});
