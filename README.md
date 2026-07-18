# AI Sales Assistant

Turns a LinkedIn profile you're **already viewing** into a decision-grade,
evidence-linked research brief — before you decide whether and how to reach out.

This repo implements the [Master Blueprint](./AI_Sales_Assistant_Master_Blueprint.md).
We build the **defensible core (research + intelligence) first**; the extension is
a thin capture client, and message generation is the commoditized last mile.

## Status

| Phase | Focus | State |
|-------|-------|-------|
| **1. Foundation** | FastAPI spine, DB models + Alembic, role-based LLM provider abstraction, end-to-end async analyze | ✅ **Done & verified** |
| **2. Research engine** | Off-LinkedIn discovery (Exa/mock) → crawl (Trafilatura/PyMuPDF) → enrichment, with provenance | ✅ **Done & verified** |
| **3. Intelligence engine** | Dual-LLM quarantine + evidence-linked brief + "should you reach out?" score | ✅ **Done & verified** |
| **4. Extension (thin client)** | MV3 passive content script → capture → analyze → render brief + draft ([`extension/`](./extension)) | ✅ **Built** (selectors need live-LinkedIn tuning) |
| **5. Message generation** | message_gen role (Claude Sonnet 5 in prod), tone/length/goal, human-in-the-loop draft | ✅ **Done & verified** |
| 6. Dashboard | Next.js prospect list + brief view + message studio | ⏳ Next |
| 7. Hardening | Rate limits, GDPR/retention, injection red-team, observability | ⏳ Planned |

The full backend loop — **capture → research → dual-LLM brief → grounded draft message** — runs
end-to-end today on the keyless mock provider. Remaining work is the Chrome extension (Phase 4),
the Next.js dashboard (Phase 6), and production hardening (Phase 7).

## Architecture

```
Chrome extension (passive)  ──HTTPS──▶  FastAPI backend
                                          ├─ POST /prospects/capture    (derived fields only; no raw HTML)
                                          ├─ POST /prospects/{id}/analyze  (async job)
                                          ├─ GET  /analyses/{id}         (poll: status + stage + brief)
                                          └─ POST /analyses/{id}/messages  (grounded draft; human sends)

Async analyze pipeline (app/intelligence/analyzer.py):
   research_company()              off-LinkedIn: discover → crawl → enrich  (provenance)
        │  untrusted web text
        ▼
   QUARANTINE LLM  (extraction role, NO tools/egress, spotlighted input)
        │  validated QuarantineFindings (structured only — injections inert)
        ▼
   context builder  →  PRIVILEGED LLM (reasoning role)  →  evidence-linked brief
        │
        ▼
   message_gen role (Sonnet 5 in prod) → draft, human-in-the-loop

LLM router: role → "provider:model"   ├─ mock (keyless) ├─ anthropic (strict tool use)
Storage: SQLite (local) / Supabase Postgres (deployed) via Alembic
         `crawled_pages` table = full off-LinkedIn page archive + per-insight provenance
```

## Database & deployment (Supabase Postgres)

Local dev uses SQLite; production uses **Supabase Postgres** (free tier). Because the
backend is built on SQLAlchemy + Alembic, the switch is just a `DATABASE_URL` change —
no model rewrites. JSON columns use **JSONB** on Postgres (compact + indexable) and
plain JSON on SQLite automatically.

- **Provisioned project:** `ai-sales-assistant` (ref `aziirmtstayrnjdnlpxw`, eu-west-2, PG 17).
  Schema is already applied (Alembic head `5d4c98978c63`) and verified end-to-end.
- **Raw content retention:** full off-LinkedIn crawled page text is archived in the
  `crawled_pages` table (`text`, `title`, `byte_size`, `content_hash`, `fetched_at`).
  The LinkedIn invariant still holds — no raw *LinkedIn* HTML is ever stored.
- **Security:** Row Level Security is **enabled** on all tables, so Supabase's public
  `anon` REST API is locked out. The backend connects with the privileged Postgres role
  (bypasses RLS by design) — all access flows through FastAPI.

To point the app at Supabase: set `DATABASE_URL` in `.env` (see `.env.example` for the
exact connection strings; grab the DB password from the Supabase dashboard).

> **Why not MongoDB?** Free tiers are ~512 MB either way (Mongo isn't "more free storage").
> This data is relational *with* JSON, so Postgres gives both real joins and JSONB
> document flexibility — and keeps Alembic + schema integrity. Large blobs, if ever
> needed, belong in object storage, not the primary DB.

**Design invariants already enforced in code:**
- No raw LinkedIn HTML is stored server-side — only derived fields (`db/models.py`).
- Every analysis claim must carry evidence + source + confidence (`schemas/analysis.py`) —
  the model structurally *cannot* invent a pain point without a supporting quote.
- LLMs are routed by **role**, not hardcoded model — swap providers via config only.
- `retention_expires_at` on prospects for GDPR/CCPA deletion from day one.

## Quickstart

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env          # optional — mock provider needs no keys
alembic upgrade head          # create the SQLite schema
uvicorn app.main:app --reload # http://localhost:8000/docs
```

Run the end-to-end spine test (no API keys required):

```bash
pytest -q
```

### Try the pipeline

```bash
# capture a prospect (what the extension will POST)
curl -X POST localhost:8000/api/v1/prospects/capture -H 'content-type: application/json' \
  -d '{"full_name":"Jane Founder","headline":"CEO at Acme","posts":[{"content":"hiring 12 engineers"}]}'

# start analysis, then poll the returned analysis_id
curl -X POST localhost:8000/api/v1/prospects/1/analyze
curl localhost:8000/api/v1/analyses/1
```

## Going to real models

Set the keys in `.env` and point the role routes at a provider, e.g.:

```
ANTHROPIC_API_KEY=sk-ant-...
MODEL_REASONING=anthropic:claude-sonnet-5
MODEL_MESSAGE_GEN=anthropic:claude-sonnet-5
```

No business logic changes — the router resolves `provider:model` at call time.
