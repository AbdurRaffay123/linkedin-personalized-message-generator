"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Analysis, Message, Prospect } from "@/lib/types";
import { Card, ScoreMeter, StatusBadge } from "@/app/ui";

export default function ProspectDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const prospectId = Number(params.id);
  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const refresh = useCallback(async () => {
    const [p, a] = await Promise.all([
      api.getProspect(prospectId),
      api.listAnalyses(prospectId),
    ]);
    setProspect(p);
    setAnalyses(a);
  }, [prospectId]);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh]);

  async function runAnalysis() {
    setRunning(true);
    setError("");
    try {
      const { analysis_id } = await api.startAnalysis(prospectId);
      // Poll until the new analysis leaves a non-terminal state.
      for (let i = 0; i < 60; i++) {
        const a = await api.getAnalysis(analysis_id);
        if (a.status === "completed" || a.status === "failed") break;
        await new Promise((r) => setTimeout(r, 1200));
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  if (error) return <Card><p className="text-sm text-red-600">{error}</p></Card>;
  if (!prospect) return <p className="text-sm text-neutral-500">Loading…</p>;

  const latestCompleted = analyses.find((a) => a.status === "completed" && a.result);

  return (
    <div className="space-y-4">
      <Link href="/" className="text-xs text-neutral-500 hover:underline">
        ← all prospects
      </Link>

      <Card>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-semibold">{prospect.full_name}</h1>
            {prospect.headline && (
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                {prospect.headline}
              </p>
            )}
            {prospect.company && (
              <p className="text-xs text-neutral-500">{prospect.company.name}</p>
            )}
          </div>
          <button
            onClick={runAnalysis}
            disabled={running}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {running ? "Analyzing…" : "Run analysis"}
          </button>
        </div>
      </Card>

      {latestCompleted?.result && (
        <BriefView analysis={latestCompleted} />
      )}

      {analyses.length > 0 && (
        <div>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
            History
          </h2>
          <div className="space-y-1">
            {analyses.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between rounded-lg border border-neutral-200 px-3 py-1.5 text-sm dark:border-neutral-800"
              >
                <span className="text-neutral-500">
                  #{a.id} · {new Date(a.created_at).toLocaleString()}
                </span>
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BriefView({ analysis }: { analysis: Analysis }) {
  const brief = analysis.result!;
  const reach = brief.should_reach_out;
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-neutral-500">
            Opportunity
          </div>
          <ScoreMeter score={brief.opportunity_score} />
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wide text-neutral-500">
            Reach out?
          </div>
          <div className="text-lg font-semibold">
            {(reach.score * 100).toFixed(0)}%
          </div>
        </div>
      </div>
      <p className="text-sm text-neutral-600 dark:text-neutral-400">
        {reach.reasoning}
      </p>

      {brief.persona_summary && (
        <section>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-500">
            Who they are
          </h3>
          <p className="text-sm">{brief.persona_summary}</p>
        </section>
      )}

      {brief.signals.length > 0 && (
        <section>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-500">
            Signals
          </h3>
          <ul className="space-y-1 text-sm">
            {brief.signals.map((s, i) => (
              <li key={i}>
                <span className="font-medium">{s.type}:</span> {s.detail}{" "}
                {s.source_url && (
                  <a
                    href={s.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    source
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {brief.pain_hypotheses.length > 0 && (
        <section>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-500">
            Pain hypotheses
          </h3>
          <ul className="space-y-2 text-sm">
            {brief.pain_hypotheses.map((h, i) => (
              <li key={i}>
                <div>{h.hypothesis}</div>
                <ul className="ml-3 mt-0.5 space-y-0.5">
                  {h.evidence.map((e, j) => (
                    <li key={j} className="text-xs text-neutral-500">
                      ↳ {e}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-500">
          Recommended angle
        </h3>
        <p className="text-sm">{brief.recommended_angle}</p>
      </section>

      <MessageStudio analysisId={analysis.id} />
    </Card>
  );
}

function MessageStudio({ analysisId }: { analysisId: number }) {
  const [tone, setTone] = useState("warm");
  const [length, setLength] = useState("short");
  const [goal, setGoal] = useState(
    "start a genuine conversation and build rapport (no hard ask)",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.listMessages(analysisId).then(setMessages).catch(() => {});
  }, [analysisId]);

  async function draft() {
    setDrafting(true);
    setErr("");
    try {
      const m = await api.createMessage(analysisId, { tone, length, goal });
      setMessages((prev) => [m, ...prev]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
    }
  }

  const field =
    "rounded-md border border-neutral-300 bg-transparent px-2 py-1 text-sm dark:border-neutral-700";

  return (
    <section className="border-t border-neutral-200 pt-4 dark:border-neutral-800">
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
        Message studio
      </h3>
      <div className="flex flex-wrap items-center gap-2">
        <select value={tone} onChange={(e) => setTone(e.target.value)} className={field}>
          <option value="warm">warm</option>
          <option value="direct">direct</option>
          <option value="curious">curious</option>
        </select>
        <select value={length} onChange={(e) => setLength(e.target.value)} className={field}>
          <option value="short">short</option>
          <option value="medium">medium</option>
        </select>
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          className={`${field} min-w-[12rem] flex-1`}
        />
        <button
          onClick={draft}
          disabled={drafting}
          className="rounded-lg border border-neutral-300 px-3 py-1 text-sm font-semibold disabled:opacity-50 dark:border-neutral-700"
        >
          {drafting ? "Drafting…" : "Draft"}
        </button>
      </div>
      {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
      <div className="mt-3 space-y-2">
        {messages.map((m) => (
          <div
            key={m.id}
            className="whitespace-pre-wrap rounded-lg bg-neutral-100 p-3 text-sm dark:bg-neutral-800"
          >
            {m.body}
            <div className="mt-1 text-xs text-neutral-500">
              {m.tone} · {m.length} · {m.model_used}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
