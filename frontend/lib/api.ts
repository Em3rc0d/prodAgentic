const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export function resolveBackendAssetUrl(assetUrl?: string | null): string | null {
  if (!assetUrl) return null;
  if (/^(https?:|data:|blob:)/i.test(assetUrl)) return assetUrl;
  return `${API}${assetUrl.startsWith("/") ? "" : "/"}${assetUrl}`;
}

export async function fetchIdeas(
  topic: string,
  style: string,
  target_language: string = "es"
): Promise<string[]> {
  const res = await fetch(`${API}/api/ideas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, style, target_language }),
  });
  if (!res.ok) throw new Error(`Ideas request failed: ${res.status}`);
  const data = await res.json();
  return data.ideas as string[];
}

export function createPipelineStream(
  idea: string,
  topic: string,
  style: string,
  target_language: string = "es",
  image_prompt_language: string = "en"
): EventSource {
  const params = new URLSearchParams({ idea, topic, style, target_language, image_prompt_language });
  return new EventSource(`${API}/api/pipeline/stream?${params}`);
}

export async function fetchPosts() {
  const res = await fetch(`${API}/api/posts`);
  if (!res.ok) throw new Error("Failed to fetch posts");
  return res.json();
}

export async function updatePostStatus(postId: string, status: string) {
  const res = await fetch(`${API}/api/posts/${postId}/status?status=${status}`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error("Failed to update status");
  return res.json();
}

export async function deletePost(postId: string) {
  const res = await fetch(`${API}/api/posts/${postId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete post");
  return res.json();
}

export type RenderStatus = "QUEUED" | "RENDERING" | "READY" | "FAILED" | "CANCELLED";

export interface VisualRenderResponse {
  render_id: string;
  status: RenderStatus;
  provider: string;
  asset_url?: string;
  url?: string; // legacy fallback
  width?: number;
  height?: number;
  prompt_used: string;
  error_message?: string;
}

export async function renderVisual(
  prompt: string,
  aspect_ratio: string = "16:9",
  style: string = "",
  run_id?: string,
  idempotency_key?: string
): Promise<VisualRenderResponse> {
  const finalIdempotencyKey = idempotency_key || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const finalRunId = run_id || finalIdempotencyKey;
  const res = await fetch(`${API}/api/visual-renders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, aspect_ratio, style, run_id: finalRunId, idempotency_key: finalIdempotencyKey }),
  });
  if (!res.ok) throw new Error(`Render request failed: ${res.status}`);
  const result = await res.json() as VisualRenderResponse;
  if (result.asset_url) result.asset_url = resolveBackendAssetUrl(result.asset_url) ?? undefined;
  return result;
}

export type ContentRunStatus =
  | "GENERATING"
  | "TEXT_READY"
  | "READY_FOR_REVIEW"
  | "APPROVED"
  | "SCHEDULED"
  | "PUBLISHING"
  | "PUBLISHED"
  | "FAILED"
  | "CANCELLED"
  | "ARCHIVED";

export type ContentRunStageStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface ContentRunStage {
  status: ContentRunStageStatus;
  output?: string | null;
  selected_model?: string | null;
  provider?: string | null;
  attempt_failures?: number;
  last_error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ContentRunVisualArtifact {
  render_id: string;
  status: RenderStatus;
  provider: string;
  asset_url?: string | null;
  width?: number | null;
  height?: number | null;
  prompt_used: string;
  requested_prompt: string;
  aspect_ratio: string;
  style: string;
  idempotency_key: string;
  error_message?: string | null;
  rendered_at: string;
}

export interface ContentRun {
  _id?: string;
  run_id: string;
  topic: string;
  style: string;
  idea: string;
  status: ContentRunStatus;
  requested_target_language?: string | null;
  resolved_target_language?: string | null;
  image_prompt_language?: string | null;
  stages: Record<string, ContentRunStage>;
  final_status?: string | null;
  final_content?: string | null;
  visual_prompt?: string | null;
  visual_render?: ContentRunVisualArtifact | null;
  post_id?: string | null;
  failure_stage?: string | null;
  failure_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentRunListResponse {
  runs: ContentRun[];
  count: number;
  message?: string;
}

export async function fetchContentRuns(limit: number = 50): Promise<ContentRunListResponse> {
  const res = await fetch(`${API}/api/content-runs?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch content runs: ${res.status}`);
  return res.json();
}

export async function fetchContentRun(runId: string): Promise<ContentRun> {
  const res = await fetch(`${API}/api/content-runs/${encodeURIComponent(runId)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch content run: ${res.status}`);
  return res.json();
}

export async function editContentRun(
  runId: string,
  changes: { final_content?: string; visual_prompt?: string }
): Promise<ContentRun> {
  const res = await fetch(`${API}/api/content-runs/${encodeURIComponent(runId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    throw new Error(`Failed to save content run (${res.status})${detail}`);
  }
  return res.json();
}
