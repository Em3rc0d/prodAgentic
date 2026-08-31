import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type EditorialVerdict =
  | "DO_NOT_PUBLISH"
  | "PUBLISHABLE"
  | "STRONG"
  | "EXCELLENT"
  | "WOULD_PUBLISH_NOW";

export type DynoSignature = "UNSIGNED" | "TRUST_FAIL" | "SIGNED_PASS";
export type TrustWheelStatus = "NOT_MEASURED" | "PASS" | "FAIL";

export interface HumanEditorialReviewInput {
  topic_fidelity: number;
  pov_strength: number;
  human_voice: number;
  usefulness: number;
  visual_message_fit: number;
  publish_readiness: number;
  verdict: EditorialVerdict;
  notes: string[];
}

export interface HumanEditorialReview extends HumanEditorialReviewInput {
  run_id: string;
  final_content_sha256: string;
  visual_asset_sha256: string;
  source: string;
  reviewed_at: string;
}

export interface DynoLoss {
  code: string;
  layer: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
  detail: string;
}

export interface DynoReport {
  dyno_version: string;
  run_id: string;
  topic: string;
  style: string;
  final_content_sha256?: string | null;
  visual_asset_sha256?: string | null;
  editorial_sensors: {
    editorial_score?: number | null;
    decision?: string | null;
    human_voice?: number | null;
    specificity?: number | null;
    ai_slop_risk?: number | null;
    hard_flags: string[];
  };
  trust_at_wheels: {
    status: TrustWheelStatus;
    grounding_decision?: string | null;
    human_grounding_verified: boolean;
    reasons: string[];
  };
  drivetrain_losses: DynoLoss[];
  human_review?: HumanEditorialReview | null;
  signature: DynoSignature;
  signature_reasons: string[];
  measured_at: string;
}

async function detailFrom(res: Response): Promise<string> {
  const payload = await res.json().catch(() => null);
  if (payload?.detail) {
    return typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
  }
  return `HTTP ${res.status}`;
}

export async function fetchDynoReport(runId: string): Promise<DynoReport> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/dyno`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Dyno report failed: ${await detailFrom(res)}`);
  return res.json();
}

export async function submitDynoReview(
  runId: string,
  input: HumanEditorialReviewInput,
): Promise<HumanEditorialReview> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/dyno/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Dyno review failed: ${await detailFrom(res)}`);
  return res.json();
}
