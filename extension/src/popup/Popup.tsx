import { useEffect, useState } from "react";
import {
  capture,
  createMessage,
  pollAnalysis,
  startAnalysis,
  testConnection,
} from "../api";
import { DEFAULT_API_BASE, getApiBase, getApiKey, saveSettings } from "../config";
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
  const tabId = tab.id;
  const ask = () =>
    chrome.tabs.sendMessage(tabId, {
      type: "EXTRACT_PROFILE",
    }) as Promise<ExtractResponse>;

  try {
    return await ask();
  } catch {
    // The declared content script isn't on this tab (it was open before the
    // extension loaded, or was just reloaded). Inject it on demand and retry —
    // so the user never has to manually reload the LinkedIn tab.
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content.js"],
      });
      return await ask();
    } catch {
      return {
        ok: false,
        error:
          "Couldn't reach the page. Reload the LinkedIn profile tab and try again.",
      };
    }
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

  // Settings: backend URL + API key, persisted to chrome.storage (no console).
  const [showSettings, setShowSettings] = useState(false);
  const [hasKey, setHasKey] = useState<boolean | null>(null);

  useEffect(() => {
    // On first open, auto-reveal Settings if no key has been configured yet.
    getApiKey().then((k) => {
      const configured = Boolean(k);
      setHasKey(configured);
      if (!configured) setShowSettings(true);
    });
  }, []);

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
        goal: "start a genuine conversation and build rapport (no hard ask)",
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
      <div className="header">
        <h1>AI Sales Assistant</h1>
        <button
          className="icon"
          title="Settings"
          aria-label="Settings"
          onClick={() => setShowSettings((s) => !s)}
        >
          ⚙
        </button>
      </div>

      {showSettings && (
        <Settings
          onSaved={(key) => {
            setHasKey(Boolean(key));
            setShowSettings(false);
          }}
        />
      )}

      {hasKey === false && !showSettings && (
        <div className="err">
          Set your backend URL &amp; API key in ⚙ Settings first.
        </div>
      )}

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

function Settings({ onSaved }: { onSaved: (apiKey: string) => void }) {
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState("");
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    getApiBase().then(setApiBase);
    getApiKey().then(setApiKey);
  }, []);

  async function save() {
    await saveSettings({ apiBase, apiKey });
    setStatus("Saved ✓");
    onSaved(apiKey.trim());
  }

  async function test() {
    setTesting(true);
    setStatus("");
    // Persist first so the test uses the values currently in the fields.
    await saveSettings({ apiBase, apiKey });
    try {
      setStatus(await testConnection());
    } catch (e) {
      setStatus(
        `Can't reach backend: ${e instanceof Error ? e.message : String(e)}`,
      );
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="card settings">
      <label>
        Backend URL
        <input
          value={apiBase}
          placeholder={DEFAULT_API_BASE}
          onChange={(e) => setApiBase(e.target.value)}
        />
      </label>
      <label>
        API key
        <input
          type="password"
          value={apiKey}
          placeholder="sk_live_…"
          onChange={(e) => setApiKey(e.target.value)}
        />
      </label>
      <div className="hint muted">
        Run <code>bash backend/start.sh</code> — it prints your API key.
      </div>
      <div className="row">
        <button onClick={save}>Save</button>
        <button className="secondary" onClick={test} disabled={testing}>
          {testing ? "Testing…" : "Test connection"}
        </button>
      </div>
      {status && <div className="stage muted">{status}</div>}
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

      {brief.persona_summary && (
        <section>
          <h2>Who they are</h2>
          <div style={{ fontSize: 12 }}>{brief.persona_summary}</div>
        </section>
      )}

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
