"""One-command end-to-end demo — see a real brief without any UI.

Usage:
    python -m app.demo

Seeds a sample prospect, runs the FULL pipeline (research → dual-LLM brief →
message) with whatever provider your .env configures (e.g. Groq), prints the
result, then deletes the sample. Uses a throwaway SQLite DB so it never touches
your real data.
"""
from __future__ import annotations

import asyncio
import os
import tempfile

# Isolate in a temp DB before importing anything that reads settings.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"


async def _main() -> None:
    from app.config import settings
    from app.db.base import Base, SessionLocal, engine
    from app.db import models  # noqa: F401
    from app.db.models import Analysis, Company, JobStatus, Post, Prospect, User
    from app.intelligence.analyzer import run_analysis
    from app.intelligence.message_gen import generate_message
    from app.schemas.analysis import AnalysisResult

    print(f"reasoning model : {settings.model_reasoning}")
    print(f"message model   : {settings.model_message_gen}")
    if settings.model_reasoning.startswith("mock:"):
        print(
            "\n⚠️  Using the MOCK provider — output will be placeholders.\n"
            "    Set a real key + MODEL_* in backend/.env (e.g. Groq) to see a real brief.\n"
        )

    Base.metadata.create_all(engine)
    db = SessionLocal()
    u = User(email="demo@local"); db.add(u); db.flush()
    c = Company(name="NovaRetail", domain="example.com"); db.add(c); db.flush()
    p = Prospect(
        user_id=u.id, company_id=c.id, full_name="Priya Menon",
        headline="VP of Engineering @ NovaRetail | Scaling e-commerce infra | ex-Amazon",
        about="I lead a 40-person eng org. Obsessed with reliability and developer "
              "velocity. We grew 5x last year and our systems are feeling it.",
        experience="VP Engineering NovaRetail 2y — scaled team 8->40, own checkout "
                    "platform. Senior Eng Manager Amazon 4y. SDE Amazon 3y.",
        education="Carnegie Mellon — MS CS. IIT Bombay — BTech.",
        skills="Distributed Systems, Kubernetes, Platform Engineering, SRE, Go",
    )
    p.posts.append(Post(content="We just had our 3rd Sev1 this quarter during peak "
                                "traffic. Reliability at scale is HARD. Hiring 6 SREs."))
    p.posts.append(Post(content="Interviewing SRE candidates all week. If you've run "
                                "incident response for high-traffic checkout, DM me."))
    db.add(p); db.flush()
    a = Analysis(prospect_id=p.id, status=JobStatus.pending); db.add(a); db.commit()
    aid = a.id
    db.close()

    print("running pipeline…\n")
    await run_analysis(aid)

    db = SessionLocal()
    done = db.get(Analysis, aid)
    if done.status != JobStatus.completed or not done.result:
        print(f"FAILED: {done.error}")
        db.close()
        return
    r = done.result
    print("=== WHO THEY ARE (persona/ICP) ===")
    print(r.get("persona_summary") or "(none)")
    print("\n=== PAIN HYPOTHESES (evidence-cited) ===")
    for h in r["pain_hypotheses"]:
        print(f"  • {h['hypothesis']}")
        for e in h["evidence"]:
            print(f"      ↳ {e}")
    print(f"\n=== RECOMMENDED ANGLE ===\n{r['recommended_angle']}")
    print(f"\nreach out: {r['should_reach_out']['score']}  |  opportunity: {r['opportunity_score']}")

    msg = await generate_message(
        AnalysisResult.model_validate(r), "Priya Menon",
        tone="direct", length="short", goal="book a 15-min call about SRE tooling",
    )
    print(f"\n=== PERSONALIZED MESSAGE ===\n{msg}")
    db.close()


def main() -> None:
    try:
        asyncio.run(_main())
    finally:
        os.unlink(_tmp.name)


if __name__ == "__main__":
    main()
