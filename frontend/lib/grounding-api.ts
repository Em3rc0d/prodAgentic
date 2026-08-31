import { secureFetch } from "./auth";
import type { ContentRun } from "./api";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type ClaimType = "FACT" | "INFERENCE" | "OPINION" | "EXPERIENCE" | "ESTIMATE" | "PREDICTION";
export type GroundingStatus = "GROUNDED" | "SUPPORTED_INFERENCE" | "OPINION" | "INSUFFICIENT_EVIDENCE" | "CONTRADICTED";
export type GroundingDecision = "PASS" | "BLOCK";

export interface ClaimProposal {
  claim_id: string;
  statement: string;
  claim_type: ClaimType;
  confidence: number;
  text_start?: number | null;
  text_end?: number | null;
}

export interface ClaimExtractionOutput {
  extraction_id: string;
  content_sha256: string;
  extractor_version: string;
  claims: ClaimProposal[];
  requires_human_completeness_review: boolean;
  created_at: string;
}

export interface ClaimExtractionReviewSnapshot {
  review_id: string;
  decision: "VERIFIED_COMPLETE" | "REJECTED";
  extraction_id: string;
  content_sha256: string;
  extraction_sha256: string;
  reviewed_at: string;
}

export interface EvidenceMatchProposal {
  claim_id: string;
  evidence_id: string;
  relation: "SUPPORTS" | "CONTRADICTS" | "INSUFFICIENT";
  confidence: number;
  rationale?: string | null;
}

export interface GroundingEvaluationDraft {
  draft_id: string;
  packet_id: string;
  content_sha256: string;
  evaluator_version: string;
  extraction_complete: boolean;
  claims: ClaimProposal[];
  evidence_matches: EvidenceMatchProposal[];
  created_at: string;
}

export interface GroundedClaim {
  claim_id: string;
  statement: string;
  claim_type: ClaimType;
  grounding_status: GroundingStatus;
  source_refs: string[];
  rationale?: string | null;
  confidence: number;
}

export interface GroundingAssessment {
  assessment_id: string;
  packet_id: string;
  content_sha256: string;
  evaluator_version: string;
  extraction_complete: boolean;
  claims: GroundedClaim[];
  evaluated_at: string;
}

export interface GroundingGate {
  policy_version: string;
  decision: GroundingDecision;
  blocking_claim_ids: string[];
  warning_claim_ids: string[];
  reasons: string[];
}

export interface GroundingReviewSnapshot {
  review_id: string;
  decision: "VERIFIED" | "REJECTED";
  source: string;
  content_sha256: string;
  source_packet_sha256: string;
  assessment_sha256: string;
  policy_version: string;
  warning_claim_ids: string[];
  reviewed_at: string;
}

export interface GenerationSourcePacketSummary {
  packet_id: string;
  workspace_id: string;
  title: string;
  summary?: string | null;
  strict_mode: boolean;
}

export type GroundingContentRun = ContentRun & {
  generation_source_packet?: GenerationSourcePacketSummary | null;
  claim_extraction?: ClaimExtractionOutput | null;
  claim_extraction_review?: ClaimExtractionReviewSnapshot | null;
  grounding_match_draft?: GroundingEvaluationDraft | null;
  grounding_assessment?: GroundingAssessment | null;
  grounding_gate?: GroundingGate | null;
  grounding_review?: GroundingReviewSnapshot | null;
};

export interface MatchEvaluateResponse {
  draft: GroundingEvaluationDraft;
  assessment: GroundingAssessment;
  gate: GroundingGate;
}

async function detailError(res: Response, prefix: string): Promise<Error> {
  const payload = await res.json().catch(() => null);
  const detail = payload?.detail
    ? `: ${typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail)}`
    : "";
  return new Error(`${prefix} (${res.status})${detail}`);
}

export async function extractClaims(runId: string): Promise<ClaimExtractionOutput> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/grounding/extract-claims`, {
    method: "POST",
  });
  if (!res.ok) throw await detailError(res, "Claim extraction failed");
  return res.json();
}

export async function reviewClaimExtraction(
  runId: string,
  decision: "VERIFIED_COMPLETE" | "REJECTED",
): Promise<ClaimExtractionReviewSnapshot> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/grounding/claim-extraction/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!res.ok) throw await detailError(res, "Claim-extraction review failed");
  return res.json();
}

export async function matchAndEvaluateCurrentEvidence(runId: string): Promise<MatchEvaluateResponse> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/grounding/match-evaluate-current`, {
    method: "POST",
  });
  if (!res.ok) throw await detailError(res, "Semantic Grounding failed");
  return res.json();
}

export async function reviewGrounding(
  runId: string,
  decision: "VERIFIED" | "REJECTED",
): Promise<GroundingContentRun> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/grounding/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!res.ok) throw await detailError(res, "Grounding review failed");
  return res.json();
}
