import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export interface ReviewAuthoritySnapshotV1 {
  tenant_id: string;
  content_id: string;
  revision_id: string;
  review_digest: string;
  revision_status: "REVIEWABLE";
  editorial_state: string;
  approval_available: boolean;
  existing_approval_id: string | null;
  profile_snapshot_digest: string;
  plan_digest: string;
  research_digest: string;
  content_digest: string;
  visual_spec_digest: string | null;
  qa_digest: string;
  asset_digests: string[];
  content: Record<string, unknown> & {
    content_spec_id: string;
    plan_id: string;
    language: string;
    title?: string | null;
    hook: string;
    body: string;
    cta?: string | null;
    hashtags: string[];
    alt_text_draft?: string | null;
    format: string;
    format_spec: unknown;
    claims_used: string[];
  };
}

export interface ApprovalBundleV2 {
  approval_id: string;
  content_id: string;
  revision_id: string;
  bundle_sha256: string;
  approved_by: string;
  approved_at: string;
}

async function jsonOrError(res: Response, fallback: string) {
  const payload = await res.json().catch(() => null);
  if (!res.ok) throw new Error(payload?.detail || `${fallback}: ${res.status}`);
  return payload;
}

export async function fetchReviewAuthority(revisionId: string): Promise<ReviewAuthoritySnapshotV1> {
  const res = await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/review-authority`, {
    cache: "no-store",
  });
  return (await jsonOrError(res, "Review authority failed")) as ReviewAuthoritySnapshotV1;
}

export async function approveRevision(revisionId: string, expectedReviewDigest: string): Promise<ApprovalBundleV2> {
  const res = await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_review_digest: expectedReviewDigest }),
  });
  const payload = await jsonOrError(res, "Approval failed");
  return payload.approval as ApprovalBundleV2;
}

export async function editRevision(
  revisionId: string,
  expectedReviewDigest: string,
  editedContent: ReviewAuthoritySnapshotV1["content"],
): Promise<{ revision: { revision_id: string }; visual_reused: boolean; invalidated: string[] }> {
  const res = await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_review_digest: expectedReviewDigest, edited_content: editedContent }),
  });
  return (await jsonOrError(res, "Edit failed")) as {
    revision: { revision_id: string };
    visual_reused: boolean;
    invalidated: string[];
  };
}

export async function downloadManualExport(approvalId: string): Promise<void> {
  const res = await secureFetch(`${API}/api/approvals/${encodeURIComponent(approvalId)}/manual-export`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Manual export failed: ${res.status}`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const safeApprovalId = approvalId.replace(/[^a-zA-Z0-9._-]+/g, "-").slice(0, 96) || "approved";
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `prodagentic-manual-${safeApprovalId}.zip`;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
