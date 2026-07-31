const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  style: string = ""
): Promise<VisualRenderResponse> {
  const idempotency_key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const run_id = idempotency_key; // use same value; server generates its own run_id if needed
  const res = await fetch(`${API}/api/visual-renders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, aspect_ratio, style, run_id, idempotency_key }),
  });
  if (!res.ok) throw new Error(`Render request failed: ${res.status}`);
  return res.json();
}
