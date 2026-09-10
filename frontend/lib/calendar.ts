import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type CalendarEntry = {
  kind: "approval" | "schedule";
  schedule_id: string | null;
  approval_id: string;
  content_id?: string;
  provider: "linkedin" | "manual_export";
  destination: string;
  scheduled_for: string | null;
  approved_at?: string;
  timezone_context: string | null;
  state: string;
  publication_id: string | null;
  reconciliation_reason: string | null;
  safe_error: string | null;
  asset_count?: number;
};

export type CalendarCapability = {
  provider: "linkedin";
  connected: boolean;
  can_publish: boolean;
  supports_text: boolean;
  supports_single_image: boolean;
  supports_multi_image: boolean;
  can_reconcile: boolean;
  external_identity?: string | null;
  api_version?: string | null;
  observed_at: string;
  reason?: string | null;
};

export type CalendarPayload = {
  start_at: string;
  end_at: string;
  capability: CalendarCapability;
  manual_export_fallback: boolean;
  entries: CalendarEntry[];
};

async function errorDetail(res: Response): Promise<string> {
  const payload = await res.json().catch(() => null);
  return payload?.detail || `Request failed (${res.status})`;
}

export async function fetchCalendar(): Promise<CalendarPayload> {
  const res = await secureFetch(`${API}/api/calendar`, { cache: "no-store" });
  if (!res.ok) throw new Error(await errorDetail(res));
  return res.json();
}

export async function createSchedule(
  approvalId: string,
  scheduledFor: string,
  timezoneContext: string,
): Promise<void> {
  const res = await secureFetch(`${API}/api/approvals/${encodeURIComponent(approvalId)}/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheduled_for: scheduledFor, timezone_context: timezoneContext, destination: "member_feed" }),
  });
  if (!res.ok) throw new Error(await errorDetail(res));
}

export async function reconcilePublication(publicationId: string): Promise<void> {
  const res = await secureFetch(`${API}/api/publications/${encodeURIComponent(publicationId)}/reconcile`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await errorDetail(res));
}

export async function connectLinkedIn(): Promise<void> {
  const res = await secureFetch(`${API}/api/connections/linkedin/connect`, { method: "POST" });
  if (!res.ok) throw new Error(await errorDetail(res));
  const payload = await res.json();
  if (!payload.authorization_url) throw new Error("LinkedIn authorization URL is unavailable");
  window.location.assign(payload.authorization_url);
}

export async function disconnectLinkedIn(): Promise<void> {
  const res = await secureFetch(`${API}/api/connections/linkedin`, { method: "DELETE" });
  if (!res.ok) throw new Error(await errorDetail(res));
}

export async function downloadManualExport(approvalId: string): Promise<void> {
  const res = await secureFetch(`${API}/api/approvals/${encodeURIComponent(approvalId)}/manual-export`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await errorDetail(res));
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = `prodagentic-manual-${approvalId}.zip`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}
