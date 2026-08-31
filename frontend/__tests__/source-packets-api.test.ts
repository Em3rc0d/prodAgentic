import {
  ACTIVE_SOURCE_PACKET_STORAGE_KEY,
  createPipelineStream,
  createQuickSourcePacket,
  fetchSourcePackets,
} from "../lib/api";


function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
}


describe("Create Studio source packet API", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    jest.clearAllMocks();
  });

  it("lists packet metadata without requiring evidence excerpts", async () => {
    global.fetch = jest.fn(() => jsonResponse({
      packets: [{
        packet_id: "packet-1",
        title: "Release evidence",
        summary: "Exact-head evidence",
        strict_mode: true,
        evidence_count: 4,
        allowed_fact_count: 3,
        allowed_inference_count: 1,
        created_at: "2026-08-30T20:00:00Z",
      }],
      count: 1,
    })) as jest.Mock;

    const result = await fetchSourcePackets(10);

    expect(result.count).toBe(1);
    expect(result.packets[0].packet_id).toBe("packet-1");
    expect(result.packets[0].allowed_fact_count).toBe(3);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/source-packets?limit=10"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("creates a strict quick packet from explicit user facts", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-source-packet" });
      }
      if (url.endsWith("/api/source-packets/quick")) {
        const payload = JSON.parse(String(init?.body));
        expect(payload.strict_mode).toBe(true);
        expect(payload.facts).toEqual(["Fact A", "Fact B"]);
        return jsonResponse({
          packet_id: "quick-1",
          workspace_id: "server-workspace",
          title: payload.title,
          summary: payload.summary,
          strict_mode: true,
          evidence: [{}, {}],
          allowed_facts: [{}, {}],
          allowed_inferences: [],
          prohibited_claims: [],
          created_at: "2026-08-30T20:00:00Z",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    const packet = await createQuickSourcePacket({
      title: "Studio evidence",
      summary: "User-provided facts",
      facts: ["Fact A", "Fact B"],
    });

    expect(packet.packet_id).toBe("quick-1");
    expect(packet.allowed_facts).toHaveLength(2);
  });

  it("binds the active session packet to the pipeline EventSource", () => {
    const created: Array<{ url: string; options?: EventSourceInit }> = [];

    class CapturingEventSource {
      url: string;
      withCredentials: boolean;
      constructor(url: string | URL, options?: EventSourceInit) {
        this.url = String(url);
        this.withCredentials = Boolean(options?.withCredentials);
        created.push({ url: this.url, options });
      }
      close() {}
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() { return true; }
      onerror = null;
      onmessage = null;
      onopen = null;
      readyState = 0;
      CONNECTING = 0;
      OPEN = 1;
      CLOSED = 2;
    }

    global.EventSource = CapturingEventSource as unknown as typeof EventSource;
    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "packet-session-1");

    createPipelineStream("idea", "topic", "educational", "es", "en");

    expect(created).toHaveLength(1);
    expect(created[0].url).toContain("source_packet_id=packet-session-1");
    expect(created[0].options?.withCredentials).toBe(true);
  });

  it("prefers an explicit packet id over a stale session selection", () => {
    let capturedUrl = "";

    class CapturingEventSource {
      constructor(url: string | URL) { capturedUrl = String(url); }
      close() {}
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() { return true; }
      onerror = null;
      onmessage = null;
      onopen = null;
      readyState = 0;
      url = "";
      withCredentials = false;
      CONNECTING = 0;
      OPEN = 1;
      CLOSED = 2;
    }

    global.EventSource = CapturingEventSource as unknown as typeof EventSource;
    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "stale-packet");

    createPipelineStream("idea", "topic", "educational", "es", "en", undefined, "explicit-packet");

    expect(capturedUrl).toContain("source_packet_id=explicit-packet");
    expect(capturedUrl).not.toContain("stale-packet");
  });
});
