// Shared types mirroring the backend contract (backend/app/schemas).

export interface CapturedPost {
  content: string;
  url?: string | null;
}

export interface CapturedProfile {
  full_name: string;
  headline?: string | null;
  about?: string | null;
  linkedin_url?: string | null;
  company?: { name: string; domain?: string | null } | null;
  posts: CapturedPost[];
}

export interface Signal {
  type: string;
  detail: string;
  source_url?: string | null;
  confidence: number;
}

export interface PainHypothesis {
  hypothesis: string;
  evidence: string[];
  confidence: number;
}

export interface AnalysisResult {
  signals: Signal[];
  pain_hypotheses: PainHypothesis[];
  recommended_angle: string;
  should_reach_out: { score: number; reasoning: string };
  opportunity_score: number;
}

export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface Analysis {
  id: number;
  prospect_id: number;
  status: JobStatus;
  stage: string | null;
  error: string | null;
  result: AnalysisResult | null;
  opportunity_score: number | null;
}

// Messages between the popup and the content script.
export type ExtractRequest = { type: "EXTRACT_PROFILE" };
export type ExtractResponse =
  | { ok: true; profile: CapturedProfile }
  | { ok: false; error: string };
