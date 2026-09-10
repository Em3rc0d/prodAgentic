import { produceContentToReview } from "@/lib/r2-production";
import { secureFetch } from "@/lib/auth";

jest.mock("@/lib/auth", () => ({ secureFetch: jest.fn() }));
const mockedSecureFetch = secureFetch as jest.MockedFunction<typeof secureFetch>;

function response(payload: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => payload } as Response;
}

function produced(format: "text" | "single_image" | "carousel" | "infographic") {
  return {
    revision: { revision_id: `revision-${format}`, status: "DRAFT" },
    content: { content_spec_id: `content-spec-${format}`, format },
  };
}

function qa(revisionId: string, reviewable = true) {
  return {
    reviewable,
    revision: { revision_id: revisionId, status: reviewable ? "REVIEWABLE" : "QA_PENDING" },
    qa_report: { failures: reviewable ? [] : ["visual.clipping.p0"] },
  };
}

describe("R2 format-aware production orchestration", () => {
  beforeEach(() => jest.clearAllMocks());

  it("text bypasses VisualSpec and Renderer and goes directly from agents to QA", async () => {
    mockedSecureFetch
      .mockResolvedValueOnce(response(produced("text"), 201))
      .mockResolvedValueOnce(response(qa("revision-text"), 201));
    const stages: string[] = [];

    const result = await produceContentToReview("content-text", (stage) => stages.push(stage));

    expect(result).toEqual({ content_id: "content-text", revision_id: "revision-text", format: "text", reviewable: true });
    expect(mockedSecureFetch).toHaveBeenCalledTimes(2);
    expect(String(mockedSecureFetch.mock.calls[0][0])).toContain("/produce-text");
    expect(String(mockedSecureFetch.mock.calls[1][0])).toContain("/qa");
    expect(stages).toEqual(["AGENTS", "QA", "REVIEWABLE"]);
  });

  it.each(["single_image", "carousel", "infographic"] as const)("%s preserves VisualSpec -> Renderer -> QA", async (format) => {
    const revisionId = `revision-${format}`;
    mockedSecureFetch
      .mockResolvedValueOnce(response(produced(format), 201))
      .mockResolvedValueOnce(response({ visual_spec: { format } }, 201))
      .mockResolvedValueOnce(response({ render_result: { assets: [{}] } }, 201))
      .mockResolvedValueOnce(response(qa(revisionId), 201));
    const stages: string[] = [];

    const result = await produceContentToReview(`content-${format}`, (stage) => stages.push(stage));

    expect(result.format).toBe(format);
    expect(mockedSecureFetch).toHaveBeenCalledTimes(4);
    expect(String(mockedSecureFetch.mock.calls[1][0])).toContain("/visual-spec");
    expect(String(mockedSecureFetch.mock.calls[2][0])).toContain("/render");
    expect(String(mockedSecureFetch.mock.calls[3][0])).toContain("/qa");
    expect(stages).toEqual(["AGENTS", "VISUAL_SPEC", "RENDER", "QA", "REVIEWABLE"]);
  });

  it("fails closed when QA does not make the revision REVIEWABLE", async () => {
    mockedSecureFetch
      .mockResolvedValueOnce(response(produced("text"), 201))
      .mockResolvedValueOnce(response(qa("revision-text", false), 201));

    await expect(produceContentToReview("content-text")).rejects.toThrow("visual.clipping.p0");
  });
});
