"""Deterministic, explainable prospect scoring.

The reasoning LLM is great at qualitative judgement but a poor calibrator — left
to itself it hands almost everyone a round "0.8 / 80". So instead of trusting a
model-invented number, we compute the "should I reach out?" score and the
opportunity score from CONCRETE features of the produced brief, and write a
reasoning string that shows the breakdown. Same evidence → same score, and the
number actually moves with how strong the case is.

Five factors (each 0..1):
  - signal_strength : how many evidence-cited signals, and how confident
  - pain_clarity    : how many pain hypotheses are backed by real evidence
  - intent          : buying/timing language in their own words (posts, signals)
  - reachability    : do they post/engage publicly (easier + warmer to reach)
  - evidence        : how much real data we actually captured (honesty guard)
"""
from __future__ import annotations

from app.intelligence.context import ProspectContext
from app.schemas.analysis import AnalysisResult, ShouldReachOut

# Timing / buying-intent language. A hit means the person is (or recently was) in
# motion — the moment outreach lands instead of bouncing.
_INTENT_TERMS = (
    "hiring", "we're hiring", "looking for", "we need", "i need", "struggling",
    "challenge", "scaling", "scale ", "migrat", "launch", "raised", "funding",
    "series a", "seed round", "bottleneck", "growth", "expanding", "roadmap",
    "audit", "optimiz", "automat", "efficiency", "backlog", "transform",
    "adopt", "rebuild", "revamp", "overhaul", "shipping", "building",
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def score_prospect(result: AnalysisResult, ctx: ProspectContext) -> AnalysisResult:
    """Recompute opportunity_score + should_reach_out from evidence, in place."""
    signals = result.signals
    pains = result.pain_hypotheses
    posts = ctx.recent_posts or []

    # --- signal_strength: volume × confidence of concrete, cited signals -------
    signal_strength = _clamp(
        0.6 * min(1.0, len(signals) / 4.0) + 0.4 * _avg([s.confidence for s in signals]),
        0.0, 1.0,
    )

    # --- pain_clarity: pains actually backed by evidence, × confidence ---------
    evidenced = [h for h in pains if h.evidence]
    evidence_items = sum(len(h.evidence) for h in evidenced)
    pain_clarity = _clamp(
        0.5 * min(1.0, len(evidenced) / 3.0)
        + 0.2 * min(1.0, evidence_items / 5.0)
        + 0.3 * _avg([h.confidence for h in evidenced]),
        0.0, 1.0,
    )

    # --- intent: buying/timing language in their OWN words + our signals -------
    haystack = " ".join(
        [*posts, *(s.detail for s in signals), *(h.hypothesis for h in pains),
         ctx.about or "", ctx.headline or ""]
    ).lower()
    intent_hits = sum(1 for t in _INTENT_TERMS if t in haystack)
    intent = _clamp(min(1.0, intent_hits / 5.0), 0.0, 1.0)

    # --- reachability: public posting = warmer, easier first touch -------------
    reachability = _clamp(min(1.0, len(posts) / 5.0), 0.0, 1.0)

    # --- evidence: how much real data underpins all of the above ---------------
    have = [
        bool(ctx.about),
        bool(ctx.experience),
        bool(posts),
        bool(ctx.quarantine.signals or ctx.firmographics),
    ]
    evidence = sum(have) / len(have)

    # --- combine ---------------------------------------------------------------
    opportunity = round(
        100 * (0.30 * signal_strength + 0.30 * pain_clarity
               + 0.25 * intent + 0.15 * evidence)
    )
    reach = (0.35 * intent + 0.25 * reachability
             + 0.25 * pain_clarity + 0.15 * evidence)

    # Honesty guard: with thin evidence, don't recommend a confident approach.
    thin = evidence < 0.34 or (not evidenced and not signals)
    if thin:
        reach = min(reach, 0.45)

    reach = _clamp(reach, 0.0, 1.0)
    opportunity = int(_clamp(opportunity, 0, 100))

    result.opportunity_score = opportunity
    result.should_reach_out = ShouldReachOut(
        score=round(reach, 2),
        reasoning=_explain(reach, thin, signals, evidenced, evidence_items,
                           intent_hits, posts),
    )
    return result


def _explain(reach, thin, signals, evidenced, evidence_items, intent_hits, posts) -> str:
    if reach >= 0.7:
        verdict = "Worth reaching out"
    elif reach >= 0.45:
        verdict = "Reasonable to reach out — keep it light and value-first"
    else:
        verdict = "Hold off — gather more before approaching"

    bits: list[str] = []
    bits.append(
        f"{len(signals)} cited signal{'s' if len(signals) != 1 else ''}"
        if signals else "no concrete signals yet"
    )
    if evidenced:
        bits.append(
            f"{len(evidenced)} evidence-backed pain point"
            f"{'s' if len(evidenced) != 1 else ''} ({evidence_items} quote"
            f"{'s' if evidence_items != 1 else ''})"
        )
    else:
        bits.append("no evidence-backed pain points")
    bits.append(
        f"{intent_hits} buying/timing cue{'s' if intent_hits != 1 else ''}"
        if intent_hits else "no timing cues"
    )
    bits.append(
        f"{len(posts)} recent post{'s' if len(posts) != 1 else ''} (publicly active)"
        if posts else "no posts captured (thin signal — try their activity feed)"
    )
    tail = " Thin evidence overall, so treat this as tentative." if thin else ""
    return f"{verdict} ({round(reach * 100)}/100). Basis: " + "; ".join(bits) + "." + tail
