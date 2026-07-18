// Passive content script (blueprint §2 architecture rules).
//
// NON-NEGOTIABLE discipline enforced here:
//   - Reads ONLY the DOM of the profile the user manually opened and is viewing.
//   - No auto-navigation, no clicking, no background jobs, no scrolling loops.
//   - Extracts derived fields only; raw HTML never leaves the page.
// It does nothing until the popup explicitly asks (user-triggered).

import type { CapturedPost, CapturedProfile, ExtractResponse } from "./types";

function text(el: Element | null | undefined): string {
  return (el?.textContent ?? "").replace(/\s+/g, " ").trim();
}

/** Try several selectors; return the first non-empty match. LinkedIn's DOM
 *  changes often, so we degrade gracefully instead of throwing. */
function firstText(selectors: string[]): string {
  for (const sel of selectors) {
    const t = text(document.querySelector(sel));
    if (t) return t;
  }
  return "";
}

function extractName(): string {
  return firstText([
    "main h1",
    "h1.text-heading-xlarge",
    "h1",
  ]);
}

function extractHeadline(): string {
  return firstText([
    "div.text-body-medium.break-words",
    "main .text-body-medium",
  ]);
}

function extractAbout(): string {
  // The "About" section: find the anchor, then read its section's body.
  const anchor = document.querySelector("#about");
  const section = anchor?.closest("section");
  if (section) {
    const body = section.querySelector(
      ".display-flex.full-width, .inline-show-more-text, span[aria-hidden='true']",
    );
    const t = text(body);
    if (t) return t;
  }
  return "";
}

function extractPosts(limit = 5): CapturedPost[] {
  // Only posts already rendered on the page — we never scroll or fetch more.
  const nodes = document.querySelectorAll(
    ".feed-shared-update-v2 .update-components-text, .feed-shared-update-v2 .break-words",
  );
  const seen = new Set<string>();
  const posts: CapturedPost[] = [];
  for (const node of Array.from(nodes)) {
    const content = text(node);
    if (content && !seen.has(content)) {
      seen.add(content);
      posts.push({ content });
      if (posts.length >= limit) break;
    }
  }
  return posts;
}

function extractCompany(): { name: string } | null {
  // Best-effort: the current-role company is often the first experience entity.
  const exp = document.querySelector(
    "#experience ~ .pvs-list__outer-container span[aria-hidden='true']",
  );
  const name = text(exp);
  return name ? { name } : null;
}

function extractProfile(): CapturedProfile {
  const full_name = extractName();
  if (!full_name) {
    throw new Error(
      "Couldn't read a profile here. Open a LinkedIn profile (linkedin.com/in/…) and try again.",
    );
  }
  return {
    full_name,
    headline: extractHeadline() || null,
    about: extractAbout() || null,
    linkedin_url: location.href.split("?")[0],
    company: extractCompany(),
    posts: extractPosts(),
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "EXTRACT_PROFILE") {
    try {
      const profile = extractProfile();
      sendResponse({ ok: true, profile } satisfies ExtractResponse);
    } catch (e) {
      sendResponse({
        ok: false,
        error: e instanceof Error ? e.message : String(e),
      } satisfies ExtractResponse);
    }
  }
  return true; // keep the message channel open for the async response
});
