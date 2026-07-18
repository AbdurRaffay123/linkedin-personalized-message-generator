# AI Sales Assistant — Dashboard (Phase 6)

Next.js (App Router) + TypeScript + Tailwind UI over the FastAPI backend.
Ties the full loop into one screen: prospect list → decision-grade brief (with
evidence links) → message studio.

## Run

```bash
cd dashboard
npm install
cp .env.local.example .env.local      # point NEXT_PUBLIC_API_BASE at the backend
npm run dev                           # http://localhost:3000
```

The backend must be running (`cd ../backend && uvicorn app.main:app --reload`).

## Pages

- `/` — prospect list (most recent first), captured via the extension.
- `/prospects/[id]` — brief view: opportunity score, "should you reach out?",
  signals (with source links), evidence-linked pain hypotheses, recommended angle,
  and a **message studio** (tone/length/goal → grounded draft). "Run analysis"
  starts a fresh analysis and polls to completion.

Data is fetched client-side, so `npm run build` needs no backend.
