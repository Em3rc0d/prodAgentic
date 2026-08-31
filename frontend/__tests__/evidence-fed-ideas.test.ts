import {
  ACTIVE_SOURCE_PACKET_STORAGE_KEY,
  createPipelineStream,
  fetchIdeas,
} from "../lib/api";


function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
}


class MockEventSource {
  url: string;
  withCredentials: boolean;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string | URL, init?: EventSourceInit) {
    this.url = String(url);
    this.withCredentials = Boolean(init?.withCredentials);
  }

  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
  CONNECTING = 0;
  OPEN = 1;
  CLOSED = 2;
  readyState = 1;
}


describe("evidence-aware idea requests", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    jest.clearAllMocks();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    global.EventSource = MockEventSource as any;
  });

  it("sends the active Evidence Dock packet as an opaque id", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
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
        return jsonResponse({
          ideas: ["1", "2", "3", "4", "5", "6", "7"],
          source_packet_id: "explicit-packet",
        });
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

  it("keeps the selected idea bound to the exact packet used by idea generation", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-ideas" });
      }
      if (url.endsWith("/api/ideas")) {
        return jsonResponse({
          ideas: ["1", "2", "3", "4", "5", "6", "7"],
          source_packet_id: "packet-A",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "packet-A");
    await fetchIdeas("prodAgentic", "storytelling", "es");

    // The user changes the dock after seeing the already-generated ideas.
    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "packet-B");
    const stream = createPipelineStream("idea 1", "prodAgentic", "storytelling", "es", "en") as unknown as MockEventSource;
    const params = new URL(stream.url).searchParams;

    expect(params.get("source_packet_id")).toBe("packet-A");
    expect(stream.withCredentials).toBe(true);
  });

  it("keeps evidence-free ideas evidence-free even if a packet is attached later", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/session")) {
        return jsonResponse({ authenticated: true, auth_enabled: true, csrf_token: "csrf-ideas" });
      }
      if (url.endsWith("/api/ideas")) {
        return jsonResponse({
          ideas: ["1", "2", "3", "4", "5", "6", "7"],
          source_packet_id: null,
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as jest.Mock;

    await fetchIdeas("Kafka", "educational", "es");
    window.sessionStorage.setItem(ACTIVE_SOURCE_PACKET_STORAGE_KEY, "late-packet");

    const stream = createPipelineStream("idea 1", "Kafka", "educational", "es", "en") as unknown as MockEventSource;
    expect(new URL(stream.url).searchParams.has("source_packet_id")).toBe(false);
  });
});