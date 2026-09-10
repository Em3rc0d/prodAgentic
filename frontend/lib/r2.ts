import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type RuntimeReadiness = {
  state: "READY" | "DEGRADED" | "UNREACHABLE";
  label: string;
  detail: string;
};

export interface ReviewQueueItem {
  revision_id: string;
  content_id: string;
  run_id: string;
  status: "QA_PENDING" | "REVIEWABLE";
  created_at: string;
  title?: string | null;
  hook?: string | null;
  format?: string | null;
  qa_report_id?: string | null;
}

export interface ReviewQueueResponse {
  revisions: ReviewQueueItem[];
  count: number;
}

export async function fetchRuntimeReadiness(): Promise<RuntimeReadiness> {
  try {
    const res = await fetch("/api/runtime-readiness", { cache: "no-store", credentials: "include" });
    if (!res.ok) throw new Error(`Readiness envelope failed: ${res.status}`);
    const payload = await res.json();
    if (!payload.reachable) {
      return {
        state: "UNREACHABLE",
        label: "Runtime unavailable",
        detail: payload.detail || "The backend readiness endpoint is unreachable.",
      };
    }
    if (payload.ready) {
      return {
        state: "READY",
        label: "Runtime ready",
        detail: payload.status || "Required runtime dependencies are ready.",
      };
    }
    return {
      state: "DEGRADED",
      label: "Runtime attention",
      detail: payload.detail || payload.status || `Readiness check returned ${payload.upstream_status ?? "unknown"}.`,
    };
  } catch (error) {
    return {
      state: "UNREACHABLE",
      label: "Runtime unavailable",
      detail: error instanceof Error ? error.message : "The runtime readiness envelope is unreachable.",
    };
  }
}

export async function fetchReviewQueue(status: "REVIEWABLE" | "QA_PENDING" = "REVIEWABLE"): Promise<ReviewQueueResponse> {
  const res = await secureFetch(`${API}/api/content-revisions?status=${encodeURIComponent(status)}&limit=100`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Review queue failed: ${res.status}`);
  }
  return res.json();
}
