import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type AnalyticsCapability = {
  schema_version: 1;
  provider: "linkedin";
  connected: boolean;
  analytics_available: boolean;
  analytics_scope_granted: boolean;
  supported_provider_metrics: string[];
  external_identity?: string | null;
  api_version?: string | null;
  observed_at: string;
  last_success_at?: string | null;
  reason?: string | null;
};

export type MetricSnapshot = {
  schema_version: 1;
  metric_snapshot_id: string;
  operation_key: string;
  tenant_id: string;
  publication_id: string;
  provider: "linkedin";
  external_post_id: string;
  captured_at: string;
  raw_available_metrics: Record<string, number>;
  normalized_metrics: Record<string, number>;
  unavailable_metrics: string[];
  freshness: {
    observed_at: string;
    expected_next_sync_at?: string | null;
    policy_version: string;
  };
  source_version: string;
  provider_api_version: string;
  collection_bucket: string;
  raw_digest: string;
  snapshot_digest: string;
  created_at: string;
};

export type AnalyticsOverview = {
  published_content_count: number;
  measured_publication_count: number;
  normalized_totals: Record<string, number | null>;
  coverage: Record<string, number>;
  impressions_or_views: number | null;
  impressions_coverage_count: number;
  interactions: number | null;
  interaction_coverage: Record<string, number>;
  last_success_at: string | null;
  freshness_state: "DEGRADED" | "NEVER_SYNCED" | "STALE" | "FRESH" | "COMPLETE_V1";
  analytics_policy_version: string;
  automatic_collection_enabled: boolean;
  capability: AnalyticsCapability;
  latest_snapshots?: MetricSnapshot[];
};

async function errorDetail(res: Response): Promise<string> {
  const payload = await res.json().catch(() => null);
  return payload?.detail || `Request failed (${res.status})`;
}

export async function fetchAnalyticsOverview(): Promise<AnalyticsOverview> {
  const res = await secureFetch(`${API}/api/analytics/overview`, { cache: "no-store" });
  if (!res.ok) throw new Error(await errorDetail(res));
  return res.json();
}

export async function enableLinkedInAnalytics(): Promise<void> {
  const res = await secureFetch(`${API}/api/connections/linkedin/analytics/enable`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await errorDetail(res));
  const payload = await res.json();
  if (!payload.authorization_url) throw new Error("LinkedIn analytics authorization URL is unavailable");
  window.location.assign(payload.authorization_url);
}

export async function collectPublicationAnalytics(publicationId: string): Promise<void> {
  const res = await secureFetch(
    `${API}/api/analytics/publications/${encodeURIComponent(publicationId)}/collect`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await errorDetail(res));
}
