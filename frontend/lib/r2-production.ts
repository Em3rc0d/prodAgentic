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

  return finishProduction(contentId, revisionId, format, onStage);
}

export async function resumeContentToReview(contentId: string, onStage?: (stage: ProductionStage) => void): Promise<ProductionOutcome> {
  const payload = await jsonOrThrow(await secureFetch(`${API}/api/content-items/${encodeURIComponent(contentId)}`, { cache: "no-store" }), "Content state unavailable");
  const item = payload?.content_item;
  if (item?.editorial_state === "PLANNED") return produceContentToReview(contentId, onStage);
  if (!item?.current_revision_id || !["PRODUCING", "READY_FOR_REVIEW", "APPROVED"].includes(item.editorial_state)) {
    throw new Error(`Production cannot resume from ${item?.editorial_state || "unknown"}. If an agent request is still running, wait and retry; otherwise create a new batch.`);
  }
  const snapshot = await fetchProductionRevision(item.current_revision_id);
  if (snapshot.revision.content_id !== contentId || snapshot.revision.status === "SUPERSEDED") {
    throw new Error("The current revision changed. Reload its authority before continuing.");
  }
  return finishProduction(contentId, snapshot.revision.revision_id, snapshot.content.payload.format, onStage, snapshot.revision);
}

async function finishProduction(
  contentId: string, revisionId: string, format: ProductionOutcome["format"],
  onStage?: (stage: ProductionStage) => void,
  revision?: ProductionRevisionSnapshot["revision"],
): Promise<ProductionOutcome> {

  if (format !== "text" && (!revision || revision.status === "DRAFT")) {
    if (!revision?.visual_spec_ref) {
      onStage?.("VISUAL_SPEC");
      await jsonOrThrow(
        await secureFetch(`${API}/api/content-revisions/${encodeURIComponent(revisionId)}/visual-spec`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }),
        "VisualSpec planning failed",
      );
    }

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
