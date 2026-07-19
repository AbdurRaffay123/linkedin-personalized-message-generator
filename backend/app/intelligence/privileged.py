"""The Privileged LLM (blueprint §5).

Does the reasoning and produces the decision-grade brief. Critically, it NEVER
sees raw untrusted web tokens — only the validated structured context built from
the Quarantine LLM's output. This is the design that breaks the "lethal trifecta":
the component with reasoning power is not exposed to untrusted content.
"""
from __future__ import annotations

from app.intelligence.context import ProspectContext
from app.llm.base import GenerateOptions, Message
from app.llm.router import router
from app.schemas.analysis import AnalysisResult

_SYSTEM = """You are a B2B sales research analyst producing a decision-grade brief.
Your job is to understand this person well enough to reach them as a human — their
role, background, how they think, what they care about, and where they hurt.

Produce:
- `persona_summary`: 2-4 sentences on who they are and how they think — seniority,
  what they're building/optimizing for, their likely ICP fit, and their probable
  communication style/mindset. Ground it in their experience, education, skills,
  About, and (most tellingly) their own posts.
- `signals`: concrete, evidence-cited observations (hiring, funding, role change,
  tech, stated priorities). NEVER invent — cite the source line/post.
- `pain_hypotheses`: their likely pain points, each with quoted evidence. Read
  between the lines of their posts and role, but every hypothesis needs support.
- `recommended_angle`: the specific way to open with them given their mindset —
  what to lead with so it lands as relevant, not spammy.
- `should_reach_out` (score 0-1 + reasoning) and `opportunity_score` (0-100):
  provide your honest read, but note these numbers are recomputed downstream from
  the concrete evidence you cite — so your real job is to surface strong, specific
  signals and evidence-backed pain, not to pick a number. Thin evidence should
  read as thin.

Prefer specific, verifiable observations over generic sales language. You are given
already-structured, trusted context. Return ONLY the structured result."""


async def run_privileged(context: ProspectContext) -> AnalysisResult:
    return await router.generate(
        "reasoning",
        [Message("system", _SYSTEM), Message("user", context.to_prompt())],
        schema=AnalysisResult,
        options=GenerateOptions(temperature=0.3, max_tokens=2048),
    )
