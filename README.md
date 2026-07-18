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
| **6. Dashboard** | Next.js prospect list + brief view (evidence links) + message studio ([`dashboard/`](./dashboard)) | ✅ **Done & verified** |
| **7. Hardening** | API-key auth + ownership, rate limits, GDPR deletion/purge, injection red-team, observability | ✅ **Done & verified** |

**All 7 phases are complete.** The full loop — **capture → research → dual-LLM brief →
grounded draft message** — runs end-to-end on the keyless mock provider across backend,
extension, and dashboard, behind a hardened, authenticated API.

## Security & operations (Phase 7)

- **Auth:** every data endpoint requires an API key (`Authorization: Bearer <key>` or
  `X-API-Key`). Only the SHA-256 hash is stored. Issue one with
  `python -m app.issue_key you@example.com`.
- **Ownership isolation:** users only see their own prospects; cross-tenant ids return
  404 (no existence leak).
- **Rate limits:** the expensive `analyze` and `capture` endpoints are rate-limited per
  user (in-process; swap in Redis for multi-worker).
- **GDPR:** `DELETE /prospects/{id}` and `DELETE /me/data` (right-to-erasure); retention
  purge job `python -m app.purge` deletes prospects past `retention_expires_at`.
- **Injection red-team:** tests assert the Quarantine LLM only ever emits validated
  structured data and the privileged reasoner never receives raw crawled tokens.
- **Observability:** every response carries an `X-Request-ID`; requests are logged with
  method/path/status/latency (never bodies or secrets). Security headers on all responses.

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

## Going to real models — including 100% FREE options

You do **not** need a paid API. The role-based router supports several
free-of-charge providers; pick one, set its key in `.env`, and point the
`MODEL_*` roles at it. No business-logic changes — the router resolves
`provider:model` at call time.

| Provider | Cost | Get a key | Example `MODEL_REASONING` |
|---|---|---|---|
| **Gemini** (recommended) | Free tier, no card | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `gemini:gemini-2.0-flash` |
| **Groq** | Free tier, no card | [console.groq.com](https://console.groq.com) | `groq:llama-3.3-70b-versatile` |
| **OpenRouter** | Free `:free` models | [openrouter.ai](https://openrouter.ai) | `openrouter:meta-llama/llama-3.3-70b-instruct:free` |
| **Ollama** | Free forever, local, offline | install [ollama.com](https://ollama.com), `ollama pull qwen2.5:7b` | `ollama:qwen2.5:7b` |
| Anthropic | Paid | — | `anthropic:claude-sonnet-5` |

Example `.env` for a fully free setup with Gemini:

```
GEMINI_API_KEY=AIza...
MODEL_EXTRACTION=gemini:gemini-2.0-flash-lite
MODEL_REASONING=gemini:gemini-2.0-flash
MODEL_MESSAGE_GEN=gemini:gemini-2.0-flash
```

See `backend/.env.example` for copy-paste blocks for each provider. Extraction
and structured briefs use JSON mode + validate-and-retry on these providers; the
evidence-linking schema still guarantees no invented pain points.
