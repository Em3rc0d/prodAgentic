import { fetchDynoReport, submitDynoReview } from "../lib/dyno-api";

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
}

describe("content dyno client", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("sends subjective human judgement only; revision identity remains server-owned", async () => {
    let payload: Record<string, unknown> | undefined;
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-dyno" });
      }
      if (url.endsWith("/api/content-runs/run-1/dyno/review")) {
        payload = JSON.parse(String(init?.body));
        expect(init?.method).toBe("POST");
        return jsonResponse({
          ...payload,
          run_id: "run-1",
          final_content_sha256: "a".repeat(64),
          visual_asset_sha256: "b".repeat(64),
          source: "explicit_human_review",
          reviewed_at: "2026-08-31T20:00:00Z",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    await submitDynoReview("run-1", {
      topic_fidelity: 0.9,
      pov_strength: 0.9,
      human_voice: 0.9,
      usefulness: 0.9,
      visual_message_fit: 0.9,
      publish_readiness: 0.9,
      verdict: "WOULD_PUBLISH_NOW",
      notes: ["Would publish."],
    });

    expect(payload).toEqual({
      topic_fidelity: 0.9,
      pov_strength: 0.9,
      human_voice: 0.9,
      usefulness: 0.9,
      visual_message_fit: 0.9,
      publish_readiness: 0.9,
      verdict: "WOULD_PUBLISH_NOW",
      notes: ["Would publish."],
    });
    expect(payload).not.toHaveProperty("run_id");
    expect(payload).not.toHaveProperty("final_content_sha256");
    expect(payload).not.toHaveProperty("visual_asset_sha256");
  });

  it("reads the current dyno report without sending review material", async () => {
    let body: BodyInit | null | undefined;
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-dyno" });
      }
      if (url.endsWith("/api/content-runs/run-1/dyno")) {
        body = init?.body;
        return jsonResponse({
          dyno_version: "content-dyno-v2",
          run_id: "run-1",
          topic: "topic",
          style: "educational",
          editorial_sensors: { hard_flags: [] },
          trust_at_wheels: { status: "NOT_MEASURED", human_grounding_verified: false, reasons: [] },
          drivetrain_losses: [],
          signature: "UNSIGNED",
          signature_reasons: [],
          measured_at: "2026-08-31T20:00:00Z",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    const report = await fetchDynoReport("run-1");
    expect(body).toBeUndefined();
    expect(report.signature).toBe("UNSIGNED");
  });
});
