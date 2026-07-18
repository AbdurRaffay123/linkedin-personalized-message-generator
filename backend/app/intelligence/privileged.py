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

Non-negotiable rules:
- Every signal and pain hypothesis MUST cite evidence; NEVER invent problems.
- Prefer specific, verifiable observations over generic sales language.
- Give an honest `should_reach_out` score in [0,1] — sometimes the right call is
  NOT to reach out; say so when the evidence is thin.
- `opportunity_score` is 0-100, reflecting fit and signal strength.
- Recommend a concrete angle grounded in the cited evidence.

You are given already-structured, trusted context. Return ONLY the structured result."""


async def run_privileged(context: ProspectContext) -> AnalysisResult:
    return await router.generate(
        "reasoning",
        [Message("system", _SYSTEM), Message("user", context.to_prompt())],
        schema=AnalysisResult,
        options=GenerateOptions(temperature=0.3, max_tokens=2048),
    )
