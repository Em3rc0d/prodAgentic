import { secureFetch } from "./auth";
import { resolveBackendAssetUrl } from "./api";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export interface RenderPreviewAssetV1 {
  asset_id: string;
  page_id: string;
  page_index: number;
  width: number;
  height: number;
  sha256: string;
  url: string;
}

export interface RenderPreviewV1 {
  revision_id: string;
  status: "QA_PENDING" | "REVIEWABLE";
  qa_state: "QA_PENDING" | "REVIEWABLE";
  format: "single_image" | "carousel" | "infographic";
  alt_text?: string | null;
  assets: RenderPreviewAssetV1[];
}

export interface QAReportSummaryV1 {
  qa_report_id: string;
  verdict: "PASS" | "PASS_WITH_WARNINGS" | "FAIL";
  warnings: string[];
  failures: string[];
  digest: string;
  recovery_attempt: number;
}

export interface RevisionQAEvidenceV1 {
  revision_id: string;
  revision_status: "QA_PENDING" | "REVIEWABLE" | "DRAFT" | "SUPERSEDED";
  readiness: "QA_PENDING" | "NEEDS_ATTENTION" | "READY_FOR_REVIEW";
  qa_report: QAReportSummaryV1 | null;
  approval_available: false;
}

export async function fetchRenderPreview(revisionId: string): Promise<RenderPreviewV1> {
  const res = await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/render-preview`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Render preview failed: ${res.status}`);
  }
  const preview = (await res.json()) as RenderPreviewV1;
  return {
    ...preview,
    assets: preview.assets
      .slice()
      .sort((a, b) => a.page_index - b.page_index)
      .map((asset) => ({ ...asset, url: resolveBackendAssetUrl(asset.url) || asset.url })),
  };
}

export async function fetchRevisionQAEvidence(revisionId: string): Promise<RevisionQAEvidenceV1> {
  const res = await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/qa-evidence`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `QA evidence failed: ${res.status}`);
  }
  return (await res.json()) as RevisionQAEvidenceV1;
}
