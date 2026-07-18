// Thin backend client used by the popup. All network egress goes to OUR backend
// only (never to LinkedIn). Poll-based because analysis is an async job.

import { getApiBase } from "./config";
import type { Analysis, CapturedProfile } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getApiBase();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export async function capture(profile: CapturedProfile): Promise<{ id: number }> {
  return req("/prospects/capture", {
    method: "POST",
    body: JSON.stringify(profile),
  });
}

export async function startAnalysis(prospectId: number): Promise<{ analysis_id: number }> {
  return req(`/prospects/${prospectId}/analyze`, { method: "POST" });
}

export async function getAnalysis(analysisId: number): Promise<Analysis> {
  return req(`/analyses/${analysisId}`);
}

/** Poll until the analysis completes or fails. */
export async function pollAnalysis(
  analysisId: number,
  onStage?: (stage: string | null) => void,
  { intervalMs = 1200, timeoutMs = 90_000 } = {},
): Promise<Analysis> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const a = await getAnalysis(analysisId);
    onStage?.(a.stage);
    if (a.status === "completed" || a.status === "failed") return a;
    if (Date.now() > deadline) throw new Error("Analysis timed out.");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export async function createMessage(
  analysisId: number,
  opts: { tone: string; length: string; goal: string },
): Promise<{ body: string }> {
  return req(`/analyses/${analysisId}/messages`, {
    method: "POST",
    body: JSON.stringify(opts),
  });
}
