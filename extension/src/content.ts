// Passive content script (blueprint §2 architecture rules).
//
// NON-NEGOTIABLE discipline enforced here:
//   - Reads ONLY the DOM of the profile the user manually opened and is viewing.
//   - No auto-navigation, no clicking, no background jobs, no scrolling loops.
//   - Extracts derived fields only; raw HTML never leaves the page.
// It does nothing until the popup explicitly asks (user-triggered).
//
// Selectors validated against a live profile (2026-07). LinkedIn ships several
// layout variants, so every field tries multiple selectors and degrades to a
// heading-based lookup (section <h2>/<h3> titles are far more stable than the
// obfuscated class names).

import type { CapturedPost, CapturedProfile, ExtractResponse } from "./types";

function text(el: Element | null | undefined): string {
  return (el?.textContent ?? "").replace(/\s+/g, " ").trim();
}

function firstText(selectors: string[], root: ParentNode = document): string {
  for (const sel of selectors) {
    const t = text(root.querySelector(sel));
    if (t) return t;
  }
  return "";
}

/** The top "intro" card that holds the name + headline. */
function introCard(): ParentNode {
  const h1 = document.querySelector("main h1");
  return h1?.closest("section") ?? document.querySelector("main") ?? document;
}

/** Read a profile section's body text by matching its heading, then strip the
 *  heading label. Resilient because section titles ("About", "Experience")
 *  change far less than class names. */
function sectionTextByHeading(titles: string[], maxLen = 2000): string {
  const heads = Array.from(document.querySelectorAll("h2, h3"));
  const wanted = titles.map((t) => t.toLowerCase());
  const heading = heads.find((el) => wanted.includes(text(el).toLowerCase()));
  const section = heading?.closest("section");
  if (!section) return "";
  let body = text(section);
  const label = text(heading);
  if (label && body.toLowerCase().startsWith(label.toLowerCase())) {
    body = body.slice(label.length).trim();
  }
  return body.slice(0, maxLen);
}

function extractName(): string {
  return firstText(["main h1", "h1.text-heading-xlarge", "h1"]);
}

function extractHeadline(): string {
  // Scope to the intro card so a generic class can't match unrelated text.
  return firstText(
    [
      ".text-body-medium.break-words",
      ".body-small.text-color-text",
      ".text-body-medium",
    ],
    introCard(),
  );
}

function extractAbout(): string {
  return sectionTextByHeading(["about"]);
}

function extractCompany(): { name: string } | null {
  // This layout exposes the current company directly.
  const direct = firstText([
    ".member-current-company",
    "button[aria-label^='Current company'] span",
  ]);
  if (direct) return { name: direct };
  // Fallback: first company link inside the Experience section.
  const heads = Array.from(document.querySelectorAll("h2, h3"));
  const exp = heads
    .find((el) => text(el).toLowerCase() === "experience")
    ?.closest("section");
  const link = exp?.querySelector("a[href*='/company/'] span[aria-hidden='true']");
  const name = text(link);
  return name ? { name } : null;
}

function extractPosts(limit = 5): CapturedPost[] {
  // Only posts already rendered — we never scroll or fetch more. Often empty on
  // a profile view (activity is lazy-loaded); the brief works without them.
  const nodes = document.querySelectorAll(
    ".feed-shared-update-v2 .update-components-text, " +
      ".feed-shared-update-v2 .break-words, " +
      "[data-urn*='activity'] .update-components-text",
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
