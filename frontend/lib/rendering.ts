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
  status: "QA_PENDING";
  qa_state: "QA_PENDING";
  format: "single_image" | "carousel" | "infographic";
  alt_text?: string | null;
  assets: RenderPreviewAssetV1[];
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
