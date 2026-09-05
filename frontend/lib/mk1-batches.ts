import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type PlannedFormat = "text" | "single_image" | "carousel" | "infographic";

export interface TargetWindowV1 {
  start_at: string;
  end_at: string;
  timezone: string;
}

export interface BatchRequestConstraintsV1 {
  campaign_goal?: string | null;
  include_topics?: string[];
  avoid_topics?: string[];
  channel_emphasis?: string | null;
  desired_format?: PlannedFormat | null;
}

export interface BatchV1 {
  batch_id: string;
  tenant_id: string;
  profile_id: string;
  profile_version: number;
  profile_snapshot_digest: string;
  target_window: TargetWindowV1;
  requested_size: number;
  selected_size: number;
  state: "PLANNED" | "PARTIAL";
  shortfall_reason?: string | null;
  summary_counts: {
    candidates_generated: number;
    candidates_blocked: number;
    candidates_rewrite: number;
    candidates_warning: number;
    selected: number;
  };
}

export interface ContentItemPlanV1 {
  content_id: string;
  batch_id: string;
  profile_id: string;
  profile_version: number;
  canonical_topic: string;
  subtopics: string[];
  angle: string;
  role: string;
  target_effect: string;
  format: PlannedFormat;
  hook_pattern: string;
  visual_pattern?: string | null;
  editorial_state: "PLANNED";
}

export interface CandidateEvaluationV1 {
  candidate: {
    candidate_id: string;
    role: string;
    topic: string;
    angle: string;
    hook_pattern: string;
    tentative_format: PlannedFormat;
  };
  novelty: {
    novelty_result_id: string;
    verdict: "PASS" | "PASS_WITH_WARNING" | "REWRITE_ANGLE" | "REPLACE_TOPIC" | "BLOCKED";
    canonical_topic: string;
    reasons: string[];
    cooldown_band: "HARD_COOLDOWN" | "STRONG_COOLDOWN" | "ELIGIBLE" | "CURRENT_BATCH";
  };
  selected: boolean;
  selection_reason: string;
}

export interface BatchPlanningResponseV1 {
  batch: BatchV1;
  content_items: ContentItemPlanV1[];
  plans: Array<{ artifact_id: string; digest: string; content_id: string }>;
  planning_trace: {
    trace_id: string;
    digest: string;
    evaluations: CandidateEvaluationV1[];
  };
  memory_count: number;
}

export async function createBatchV1(
  profileId: string,
  input: {
    target_window: TargetWindowV1;
    requested_size: number;
    constraints?: BatchRequestConstraintsV1;
  },
): Promise<BatchPlanningResponseV1> {
  const res = await secureFetch(`${API}/api/profiles/${encodeURIComponent(profileId)}/batches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...input, constraints: input.constraints ?? {} }),
  });
  if (!res.ok) throw new Error(`Batch planning failed: ${res.status}`);
  return res.json();
}

export async function fetchBatchV1(batchId: string): Promise<BatchPlanningResponseV1> {
  const res = await secureFetch(`${API}/api/batches/${encodeURIComponent(batchId)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch Batch: ${res.status}`);
  return res.json();
}
