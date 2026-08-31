import { ACTIVE_SOURCE_PACKET_STORAGE_KEY, fetchIdeas } from "../lib/api";


function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
}


describe("evidence-aware idea requests", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    jest.clearAllMocks();
  });

  it("sends the active Evidence Dock packet as an opaque id", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-ideas" });
      }
      if (url.endsWith("/api/ideas")) {
        return jsonResponse({
          ideas: ["1", "2", "3", "4", "5", "6", "7"],
          source_packet_id: "packet-session",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "packet-session");
    await fetchIdeas("prodAgentic", "educational", "es");

    const ideasCall = (global.fetch as jest.Mock).mock.calls.find(([input]) => String(input).endsWith("/api/ideas"));
    expect(ideasCall).toBeDefined();
    const payload = JSON.parse(String(ideasCall![1].body));
    expect(payload.source_packet_id).toBe("packet-session");
    expect(payload).not.toHaveProperty("evidence");
    expect(payload).not.toHaveProperty("allowed_facts");
  });

  it("prefers an explicit packet id over stale session state", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-ideas" });
      }
      if (url.endsWith("/api/ideas")) {
        return jsonResponse({ ideas: ["1", "2", "3", "4", "5", "6", "7"] });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "stale-packet");
    await fetchIdeas("prodAgentic", "educational", "es", undefined, "explicit-packet");

    const ideasCall = (global.fetch as jest.Mock).mock.calls.find(([input]) => String(input).endsWith("/api/ideas"));
    const payload = JSON.parse(String(ideasCall![1].body));
    expect(payload.source_packet_id).toBe("explicit-packet");
    expect(JSON.stringify(payload)).not.toContain("stale-packet");
  });
});
