const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export function resolveBackendAssetUrl(assetUrl?: string | null): string | null {
  if (!assetUrl) return null;
  if (/^(https?:|data:|blob:)/i.test(assetUrl)) return assetUrl;
  return `${API}${assetUrl.startsWith("/") ? "" : "/"}${assetUrl}`;
}

export async function fetchIdeas(
  topic: string,
  style: string,
  target_language: string = "es",
  content_profile_id?: string
): Promise<string[]> {
  const res = await fetch(`${API}/api/ideas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, style, target_language, content_profile_id }),
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
  image_prompt_language: string = "en",
  content_profile_id?: string
): EventSource {
  const params = new URLSearchParams({ idea, topic, style, target_language, image_prompt_language });
  if (content_profile_id) params.set("content_profile_id", content_profile_id);
  return new EventSource(`${API}/api/pipeline/stream?${params}`);
}

export async function fetchPosts() {
  const res = await fetch(`${API}/api/posts`);
  if (!res.ok) throw new Error("Failed to fetch posts");
  return res.json();
}

export async function updatePostStatus(postId: string, status: string) {
  const res = await fetch(`${API}/api/posts/${postId}/status?status=${status}`, { method: "PATCH" });
  if (!res.ok) throw new Error("Failed to update status");
  return res.json();
}

export async function deletePost(postId: string) {
  const res = await fetch(`${API}/api/posts/${postId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete post");
  return res.json();
}

export interface ContentProfile {
  profile_id: string;
  name: string;
  display_name?: string | null;
  positioning?: string | null;
  audience: string[];
  voice: string[];
  core_topics: string[];
  excluded_topics: string[];
  target_language: "es" | "en" | "pt";
  image_prompt_language: "es" | "en" | "pt";
  min_words: number;
  max_words: number;
  preferred_style: string;
  visual_enabled: boolean;
  default_aspect_ratio: "16:9" | "1:1" | "4:5";
  default_visual_style: string;
  forbidden_claims: string[];
  banned_phrases: string[];
  brand_constraints: string[];
  is_default: boolean;
  version: number;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export type ContentProfileInput = Omit<ContentProfile, "profile_id" | "version" | "archived" | "created_at" | "updated_at">;

export async function fetchContentProfiles(): Promise<{ profiles: ContentProfile[]; count: number }> {
  const res = await fetch(`${API}/api/content-profiles`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch content profiles: ${res.status}`);
  return res.json();
}

export async function createContentProfile(profile: ContentProfileInput): Promise<ContentProfile> {
  const res = await fetch(`${API}/api/content-profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Error(`Failed to create content profile: ${res.status}`);
  return res.json();
}

export async function updateContentProfile(profileId: string, changes: Partial<ContentProfileInput> & { archived?: boolean }): Promise<ContentProfile> {
  const res = await fetch(`${API}/api/content-profiles/${encodeURIComponent(profileId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!res.ok) throw new Error(`Failed to update content profile: ${res.status}`);
  return res.json();
}

export async function setDefaultContentProfile(profileId: string): Promise<ContentProfile> {
  const res = await fetch(`${API}/api/content-profiles/${encodeURIComponent(profileId)}/default`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to set default profile: ${res.status}`);
  return res.json();
}

export type RenderStatus = "QUEUED" | "RENDERING" | "READY" | "FAILED" | "CANCELLED";

export interface VisualRenderResponse {
  render_id: string;
  status: RenderStatus;
  provider: string;
  asset_url?: string;
  asset_sha256?: string;
  url?: string;
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
  | "GENERATING" | "TEXT_READY" | "READY_FOR_REVIEW" | "APPROVED" | "SCHEDULED"
  | "PUBLISHING" | "PUBLISHED" | "FAILED" | "CANCELLED" | "ARCHIVED";

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
  asset_sha256?: string | null;
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

export interface ContentRunApprovalSnapshot {
  approval_id: string;
  approved_at: string;
  source: "explicit_user_action" | string;
  include_visual: boolean;
  final_content: string;
  final_content_sha256: string;
  visual_render?: ContentRunVisualArtifact | null;
  visual_render_sha256?: string | null;
  bundle_sha256: string;
}

export interface ContentRun {
  _id?: string;
  run_id: string;
  topic: string;
  style: string;
  idea: string;
  status: ContentRunStatus;
  content_profile_id?: string | null;
  content_profile_snapshot?: Record<string, unknown> | null;
  requested_target_language?: string | null;
  resolved_target_language?: string | null;
  image_prompt_language?: string | null;
  stages: Record<string, ContentRunStage>;
  final_status?: string | null;
  final_content?: string | null;
  visual_prompt?: string | null;
  visual_render?: ContentRunVisualArtifact | null;
  approval?: ContentRunApprovalSnapshot | null;
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

export async function editContentRun(runId: string, changes: { final_content?: string; visual_prompt?: string }): Promise<ContentRun> {
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

export async function approveContentRun(runId: string, includeVisual: boolean): Promise<ContentRun> {
  const res = await fetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_visual: includeVisual }),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    throw new Error(`Failed to approve content run (${res.status})${detail}`);
  }
  return res.json();
}
