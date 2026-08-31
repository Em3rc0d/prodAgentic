import {
  extractClaims,
  matchAndEvaluateCurrentEvidence,
  reviewClaimExtraction,
  reviewGrounding,
} from "../lib/grounding-api";


function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
}


describe("human Grounding review client", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("asks the server to match/evaluate current evidence without sending evidence or relation proposals", async () => {
    let capturedBody: BodyInit | null | undefined;
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-review" });
      }
      if (url.endsWith("/api/content-runs/run-1/grounding/match-evaluate-current")) {
        capturedBody = init?.body;
        expect(init?.method).toBe("POST");
        return jsonResponse({
          draft: { draft_id: "d1", packet_id: "p1", claims: [], evidence_matches: [] },
          assessment: { assessment_id: "a1", packet_id: "p1", claims: [] },
          gate: { decision: "BLOCK", blocking_claim_ids: [], warning_claim_ids: [], reasons: ["empty"] },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    const result = await matchAndEvaluateCurrentEvidence("run-1");

    expect(capturedBody).toBeUndefined();
    expect(result.gate.decision).toBe("BLOCK");
  });

  it("claim extraction review sends only the explicit human decision", async () => {
    let payload: unknown;
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-review" });
      }
      if (url.endsWith("/grounding/claim-extraction/review")) {
        payload = JSON.parse(String(init?.body));
        return jsonResponse({
          review_id: "r1",
          decision: "VERIFIED_COMPLETE",
          extraction_id: "e1",
          content_sha256: "a".repeat(64),
          extraction_sha256: "b".repeat(64),
          reviewed_at: "2026-08-31T05:00:00Z",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    await reviewClaimExtraction("run-1", "VERIFIED_COMPLETE");
    expect(payload).toEqual({ decision: "VERIFIED_COMPLETE" });
  });

  it("Grounding verification sends only the explicit human decision", async () => {
    let payload: unknown;
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-review" });
      }
      if (url.endsWith("/grounding/review")) {
        payload = JSON.parse(String(init?.body));
        return jsonResponse({ run_id: "run-1", status: "READY_FOR_REVIEW" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    await reviewGrounding("run-1", "VERIFIED");
    expect(payload).toEqual({ decision: "VERIFIED" });
  });

  it("claim extraction endpoint remains proposal-only from the client", async () => {
    let capturedBody: BodyInit | null | undefined;
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-review" });
      }
      if (url.endsWith("/grounding/extract-claims")) {
        capturedBody = init?.body;
        return jsonResponse({
          extraction_id: "e1",
          content_sha256: "a".repeat(64),
          extractor_version: "v1",
          claims: [],
          requires_human_completeness_review: true,
          created_at: "2026-08-31T05:00:00Z",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    await extractClaims("run-1");
    expect(capturedBody).toBeUndefined();
  });
});
