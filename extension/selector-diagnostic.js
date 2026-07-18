// LinkedIn selector diagnostic — paste into the browser console (F12 → Console)
// while viewing a linkedin.com/in/… profile, then copy the printed JSON back.
// Read-only: it only reads the DOM you're already looking at. It clicks nothing.
(() => {
  const t = (el) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
  const first = (sels) => {
    for (const s of sels) {
      const v = t(document.querySelector(s));
      if (v) return { selector: s, value: v.slice(0, 140) };
    }
    return null;
  };
  const report = {
    url: location.href,
    docTitle: document.title,
    name: first(["main h1", "h1.text-heading-xlarge", "h1"]),
    headline: first([
      "div.text-body-medium.break-words",
      "main .text-body-medium",
    ]),
    aboutAnchorPresent: !!document.querySelector("#about"),
    about: (() => {
      const a = document.querySelector("#about");
      const s = a?.closest("section");
      const b = s?.querySelector(
        ".display-flex.full-width, .inline-show-more-text, span[aria-hidden='true']",
      );
      return t(b).slice(0, 180) || null;
    })(),
    postNodeCount: document.querySelectorAll(
      ".feed-shared-update-v2 .update-components-text, .feed-shared-update-v2 .break-words",
    ).length,
    experienceAnchorPresent: !!document.querySelector("#experience"),
    // Fallback diagnostics so selectors can be repaired if the above miss:
    allH1: [...document.querySelectorAll("h1")].map((h) => t(h)).slice(0, 3),
    sectionAnchors: [...document.querySelectorAll("section[id], div[id]")]
      .map((s) => s.id)
      .filter(Boolean)
      .slice(0, 20),
  };
  console.log(JSON.stringify(report, null, 2));
  return report;
})();
