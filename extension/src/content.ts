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

/** Derive the person's name from the page <title>. LinkedIn titles look like
 *  "(3) Jane Doe | LinkedIn" or "Jane Doe - Senior PM at Acme | LinkedIn".
 *  A resilient last resort when class names / h1 structure change. */
function nameFromTitle(): string {
  let t = document.title || "";
  t = t.replace(/^\(\d+\+?\)\s*/, ""); // strip unread-count badge "(3) "
  t = t.split("|")[0]; // drop " | LinkedIn"
  t = t.split(" - ")[0]; // drop " - <headline>"
  t = t.trim();
  if (/^linkedin$/i.test(t)) return "";
  return t;
}

function extractName(): string {
  // 1) Preferred: the profile intro heading, across known layout variants.
  const bySelector = firstText([
    "main h1",
    "h1.text-heading-xlarge",
    "section.artdeco-card h1",
    "h1",
  ]);
  if (bySelector) return bySelector;
  // 2) Any non-empty <h1> anywhere on the page.
  for (const h of Array.from(document.querySelectorAll("h1"))) {
    const t = text(h);
    if (t) return t;
  }
  // 3) Last resort: parse the tab title.
  return nameFromTitle();
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

function extractExperience(): string {
  return sectionTextByHeading(["experience"]);
}

function extractEducation(): string {
  return sectionTextByHeading(["education"]);
}

function extractSkills(): string {
  return sectionTextByHeading(["skills"], 800);
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

function extractPosts(limit = 8): CapturedPost[] {
  // Only posts already RENDERED on the page — we never scroll or navigate. The
  // profile "Activity" card shows just 1–2 recent posts; for real coverage the
  // user should open the person's Activity/Posts feed and scroll a little before
  // clicking Analyze (their action, never ours). Posts are the strongest signal
  // of mindset & pain, so we cast a wide net across LinkedIn's post-text markup.
  const POST_TEXT_SELECTORS = [
    ".feed-shared-update-v2 .update-components-text",
    ".update-components-update-v2__commentary",
    ".feed-shared-inline-show-more-text",
    ".feed-shared-update-v2 .break-words",
    "[data-urn*='activity'] .update-components-text",
    ".update-components-text",
  ].join(", ");

  const seen = new Set<string>();
  const posts: CapturedPost[] = [];
  for (const node of Array.from(document.querySelectorAll(POST_TEXT_SELECTORS))) {
    // Skip nodes nested inside an already-captured post (avoids duplicates from
    // overlapping selectors matching parent + child).
    const content = text(node);
    if (!content || content.length <= 20) continue;
    // Collapse near-duplicates: a truncated "…more" copy of a longer capture.
    if (seen.has(content)) continue;
    let dup = false;
    for (const prev of seen) {
      if (prev.includes(content) || content.includes(prev)) {
        dup = true;
        break;
      }
    }
    if (dup) continue;
    seen.add(content);
    posts.push({ content });
    if (posts.length >= limit) break;
  }
  return posts;
}

/** When post capture comes back empty, probe candidate LinkedIn post-markup
 *  patterns and report how many each matches. Lets us pinpoint the right
 *  selector from the popup, without needing the DevTools console. */
function postsDiagnostic(): string {
  const probes: [string, string][] = [
    ["feed-shared-update-v2", ".feed-shared-update-v2"],
    ["update-components-text", ".update-components-text"],
    ["v2__commentary", ".update-components-update-v2__commentary"],
    ["inline-show-more-text", ".feed-shared-inline-show-more-text"],
    ["data-urn*activity", "[data-urn*='activity']"],
    ["data-urn*share", "[data-urn*='share']"],
    ["data-id*activity", "[data-id*='urn:li:activity']"],
    ["any data-urn", "[data-urn]"],
    ["role=article", "[role='article']"],
    ["break-words", ".break-words"],
  ];
  const hits = probes
    .map(([label, sel]) => {
      let n = 0;
      try {
        n = document.querySelectorAll(sel).length;
      } catch {
        n = -1;
      }
      return `${label}=${n}`;
    })
    .join(" ");
  return `[posts-diag] path=${location.pathname} ${hits}`;
}

/** Canonical profile URL — the same identity whether the user is on the main
 *  profile (/in/slug) or a subpage (/in/slug/recent-activity/all). Lets the
 *  backend merge an about/experience capture with a posts capture of the same
 *  person instead of creating two prospects. */
function canonicalProfileUrl(): string {
  const m = location.pathname.match(/\/in\/([^/]+)/);
  if (m) return `https://www.linkedin.com/in/${m[1]}/`;
  return location.href.split("?")[0];
}

function extractProfile(): CapturedProfile {
  const full_name = extractName();
  if (!full_name) {
    // Surface a compact diagnostic so we can tune selectors without the console.
    const h1s = document.querySelectorAll("h1").length;
    const firstH1 = text(document.querySelector("h1")).slice(0, 40);
    throw new Error(
      "Couldn't read a profile here. Make sure you're on a linkedin.com/in/… " +
        "page that has finished loading, then try again.\n" +
        `[diag] url=${location.pathname} title="${document.title.slice(0, 60)}" ` +
        `h1s=${h1s} firstH1="${firstH1}"`,
    );
  }
  return {
    full_name,
    headline: extractHeadline() || null,
    about: extractAbout() || null,
    linkedin_url: canonicalProfileUrl(),
    company: extractCompany(),
    experience: extractExperience() || null,
    education: extractEducation() || null,
    skills: extractSkills() || null,
    posts: extractPosts(),
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "EXTRACT_PROFILE") {
    try {
      const profile = extractProfile();
      // Surface a post-markup probe when nothing was captured, so selectors can
      // be tuned to the live DOM from the popup.
      const notes = profile.posts.length === 0 ? postsDiagnostic() : undefined;
      sendResponse({ ok: true, profile, notes } satisfies ExtractResponse);
    } catch (e) {
      sendResponse({
        ok: false,
        error: e instanceof Error ? e.message : String(e),
      } satisfies ExtractResponse);
    }
  }
  return true; // keep the message channel open for the async response
});
