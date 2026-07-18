import { useState } from "react";
import {
  capture,
  createMessage,
  pollAnalysis,
  startAnalysis,
} from "../api";
import type { AnalysisResult, ExtractResponse } from "../types";

type Phase = "idle" | "working" | "done" | "error";

async function extractFromActiveTab(): Promise<ExtractResponse> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.includes("linkedin.com/in/")) {
    return {
      ok: false,
      error: "Open a LinkedIn profile (linkedin.com/in/…), then click Analyze.",
    };
  }
  try {
    return (await chrome.tabs.sendMessage(tab.id, {
      type: "EXTRACT_PROFILE",
    })) as ExtractResponse;
  } catch {
    return {
      ok: false,
      error:
        "Couldn't reach the page. Reload the LinkedIn profile tab and try again.",
    };
  }
}

export function Popup() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [stage, setStage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [brief, setBrief] = useState<AnalysisResult | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [drafting, setDrafting] = useState(false);

  async function run() {
    setPhase("working");
    setError("");
    setBrief(null);
    setDraft("");
    try {
      setStage("reading profile");
      const res = await extractFromActiveTab();
      if (!res.ok) throw new Error(res.error);

      setStage("capturing");
      const { id } = await capture(res.profile);

      setStage("starting analysis");
      const { analysis_id } = await startAnalysis(id);
      setAnalysisId(analysis_id);

      const analysis = await pollAnalysis(analysis_id, (s) =>
        setStage(s ? `analyzing: ${s}` : "analyzing"),
      );
      if (analysis.status === "failed" || !analysis.result) {
        throw new Error(analysis.error ?? "Analysis failed.");
      }
      setBrief(analysis.result);
      setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  }

  async function draftMessage() {
    if (analysisId == null) return;
    setDrafting(true);
    try {
      const { body } = await createMessage(analysisId, {
        tone: "warm",
        length: "short",
        goal: "book a short call",
      });
      setDraft(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
    }
  }

  return (
    <div>
      <h1>AI Sales Assistant</h1>
      <button onClick={run} disabled={phase === "working"}>
        {phase === "working" ? "Working…" : "Analyze this profile"}
      </button>
      {phase === "working" && <div className="stage muted">{stage}</div>}
      {phase === "error" && <div className="err">{error}</div>}

      {brief && <Brief brief={brief} />}

      {brief && (
        <section>
          <h2>Outreach draft</h2>
          <button
            className="secondary"
            onClick={draftMessage}
            disabled={drafting}
          >
            {drafting ? "Drafting…" : "Draft a message"}
          </button>
          {draft && (
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} />
          )}
        </section>
      )}
    </div>
  );
}

function Brief({ brief }: { brief: AnalysisResult }) {
  const reach = brief.should_reach_out;
  return (
    <div className="card">
      <div>
        <span className="score">{brief.opportunity_score}</span>
        <span className="muted"> / 100 opportunity</span>
        <span className="pill">
          reach out: {(reach.score * 100).toFixed(0)}%
        </span>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
        {reach.reasoning}
      </div>

      {brief.signals.length > 0 && (
        <section>
          <h2>Signals</h2>
          {brief.signals.map((s, i) => (
            <div key={i} style={{ fontSize: 12 }}>
              <b>{s.type}:</b> {s.detail}
            </div>
          ))}
        </section>
      )}

      {brief.pain_hypotheses.length > 0 && (
        <section>
          <h2>Pain hypotheses</h2>
          {brief.pain_hypotheses.map((h, i) => (
            <div key={i} style={{ fontSize: 12, marginBottom: 4 }}>
              {h.hypothesis}
              {h.evidence.map((e, j) => (
                <div className="evi" key={j}>
                  ↳ {e}
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      <section>
        <h2>Recommended angle</h2>
        <div style={{ fontSize: 12 }}>{brief.recommended_angle}</div>
      </section>
    </div>
  );
}
