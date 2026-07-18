// Browser-side client for the FastAPI backend. Base URL is configurable so the
// same build works against localhost or a deployed API.
import type { Analysis, Message, Prospect } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listProspects: () => req<Prospect[]>("/prospects"),
  getProspect: (id: number) => req<Prospect>(`/prospects/${id}`),
  listAnalyses: (prospectId: number) =>
    req<Analysis[]>(`/prospects/${prospectId}/analyses`),
  getAnalysis: (id: number) => req<Analysis>(`/analyses/${id}`),
  listMessages: (analysisId: number) =>
    req<Message[]>(`/analyses/${analysisId}/messages`),
  startAnalysis: (prospectId: number) =>
    req<{ analysis_id: number }>(`/prospects/${prospectId}/analyze`, {
      method: "POST",
    }),
  createMessage: (
    analysisId: number,
    opts: { tone: string; length: string; goal: string },
  ) =>
    req<Message>(`/analyses/${analysisId}/messages`, {
      method: "POST",
      body: JSON.stringify(opts),
    }),
};
