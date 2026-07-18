// Mirrors the backend contract (backend/app/schemas).

export interface Company {
  id: number;
  name: string;
  domain: string | null;
}

export interface Prospect {
  id: number;
  full_name: string;
  headline: string | null;
  linkedin_url: string | null;
  captured_at: string;
  company: Company | null;
}

export interface Signal {
  type: string;
  detail: string;
  source_url: string | null;
  confidence: number;
}

export interface PainHypothesis {
  hypothesis: string;
  evidence: string[];
  confidence: number;
}

export interface AnalysisResult {
  persona_summary?: string;
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
  created_at: string;
  completed_at: string | null;
}

export interface Message {
  id: number;
  analysis_id: number;
  body: string;
  tone: string | null;
  length: string | null;
  goal: string | null;
  model_used: string | null;
  edited_by_user: boolean;
  created_at: string;
}
