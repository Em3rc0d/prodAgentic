const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export interface AuthSession {
  authenticated: boolean;
  auth_enabled: boolean;
  csrf_token?: string | null;
  expires_at?: number;
}

let csrfToken: string | null = null;

export async function loadSession(): Promise<AuthSession> {
  const response = await fetch(`${API}/api/auth/session`, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error(`Session unavailable: ${response.status}`);
  const session = await response.json() as AuthSession;
  csrfToken = session.csrf_token ?? null;
  return session;
}

export async function login(username: string, password: string): Promise<AuthSession> {
  const response = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error(response.status === 401 ? "Invalid username or password" : `Login failed: ${response.status}`);
  const session = await response.json() as AuthSession;
  csrfToken = session.csrf_token ?? null;
  return session;
}

export async function secureFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (!csrfToken) await loadSession();
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(input, { ...init, headers, credentials: "include" });
  if (response.status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new Event("prodagentic:unauthorized"));
  }
  return response;
}
