import { secureFetch } from "./auth";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type ProductionStage = "AGENTS" | "VISUAL_SPEC" | "RENDER" | "QA" | "REVIEWABLE";

export interface ProductionOutcome {
  content_id: string;
  revision_id: string;
  format: "text" | "single_image" | "carousel" | "infographic";
  reviewable: boolean;
}

export interface ProductionRevisionSnapshot {
  revision: {
    revision_id: string;
    content_id: string;
    status: "DRAFT" | "QA_PENDING" | "REVIEWABLE" | "SUPERSEDED";
    visual_spec_ref?: string | null;
    asset_refs?: string[];
  };
  content: {
    artifact_type: string;
    digest: string;
    payload: {
      content_spec_id: string;
      title?: string | null;
      hook: string;
      body: string;
      cta?: string | null;
      format: "text" | "single_image" | "carousel" | "infographic";
    };
  };
}

async function jsonOrThrow(response: Response, label: string) {
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail || `${label}: ${response.status}`);
  return payload;
}

export async function produceContentToReview(
  contentId: string,
  onStage?: (stage: ProductionStage) => void,
): Promise<ProductionOutcome> {
  onStage?.("AGENTS");
  const produced = await jsonOrThrow(
    await secureFetch(`${API}/api/content-items/${encodeURIComponent(contentId)}/produce-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }),
    "Structured production failed",
  );

  const revisionId = String(produced.revision?.revision_id || "");
  const format = produced.content?.format as ProductionOutcome["format"];
  if (!revisionId || !["text", "single_image", "carousel", "infographic"].includes(format)) {
    throw new Error("Structured production returned an incomplete revision contract.");
  }

  if (format !== "text") {
    onStage?.("VISUAL_SPEC");
    await jsonOrThrow(
      await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/visual-spec`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
      "VisualSpec planning failed",
    );

    onStage?.("RENDER");
    await jsonOrThrow(
      await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
      "Render failed",
    );
  }

  onStage?.("QA");
  const qa = await jsonOrThrow(
    await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }),
    "QA execution failed",
  );
  if (!qa.reviewable || qa.revision?.status !== "REVIEWABLE") {
    const failures = qa.qa_report?.failures?.length ? ` (${qa.qa_report.failures.join(", ")})` : "";
    throw new Error(`QA retained this revision for attention${failures}.`);
  }

  onStage?.("REVIEWABLE");
  return { content_id: contentId, revision_id: revisionId, format, reviewable: true };
}

export async function fetchProductionRevision(revisionId: string): Promise<ProductionRevisionSnapshot> {
  const response = await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}`, { cache: "no-store" });
  return (await jsonOrThrow(response, "Revision authority failed")) as ProductionRevisionSnapshot;
}
