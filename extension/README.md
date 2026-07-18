# AI Sales Assistant — Chrome Extension (Phase 4)

A **passive, user-triggered** MV3 capture client. It reads only the DOM of the
LinkedIn profile you're already viewing, extracts derived fields, and sends them
to the backend to produce a decision-grade brief. It never auto-navigates,
scrolls, clicks, or runs background jobs — that discipline is the legal posture
(blueprint §2), not a nicety.

## Build & load

```bash
cd extension
npm install
npm run build        # → dist/   (npm run watch for live rebuilds)
```

Then in Chrome:
1. Go to `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select the `extension/dist` folder.
3. Start the backend (`cd ../backend && uvicorn app.main:app --reload`).
4. Open a `linkedin.com/in/…` profile, click the extension icon → **Analyze this profile**.

## Pointing at a deployed backend

The default backend is `http://localhost:8000`. To use another URL without
rebuilding, set it in the extension's storage from its service-worker console:

```js
chrome.storage.local.set({ apiBase: "https://your-api.example/api/v1" })
```

Also add that host to `host_permissions` in `public/manifest.json` and rebuild.

## Architecture

```
content.ts   passive DOM reader (only when the popup asks) → derived fields
popup/       React UI: Analyze → capture → poll → render evidence-linked brief → draft message
background.ts minimal MV3 service worker (extension point; no scraping logic)
api.ts       talks ONLY to our backend, never to LinkedIn
```

## ⚠️ Selector caveat

LinkedIn's DOM class names change frequently and are obfuscated. The selectors in
`src/content.ts` are best-effort with fallbacks; they will need validation/tuning
against the live site (which can't be done from CI). The *architecture* — passive,
derived-only, user-triggered — is the stable part; the selectors are the
maintenance surface.
