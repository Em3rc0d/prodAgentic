"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { loadSession, login } from "@/lib/auth";

export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "authenticated" | "anonymous">("loading");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const checkSession = useCallback(() => {
    loadSession().then(() => setState("authenticated")).catch(() => setState("anonymous"));
  }, []);

  useEffect(() => {
    checkSession();
    const handleUnauthorized = () => {
      setState("loading");
      checkSession();
    };
    window.addEventListener("prodagentic:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("prodagentic:unauthorized", handleUnauthorized);
  }, [checkSession]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSubmitting(true);
    setError("");
    try {
      await login(String(data.get("username") || ""), String(data.get("password") || ""));
      setState("authenticated");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (state === "loading") return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>Checking secure session…</main>;
  if (state === "authenticated") return <>{children}</>;

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <form onSubmit={submit} style={{ width: "min(420px, 100%)", display: "grid", gap: 16, padding: 28, border: "1px solid var(--border)", borderRadius: 16, background: "var(--surface)" }}>
        <div><div style={{ fontSize: 13, opacity: .7 }}>prodAgentic</div><h1 style={{ margin: "6px 0" }}>Secure workspace</h1><p style={{ margin: 0, opacity: .75 }}>Sign in to operate the publishing identity.</p></div>
        <label style={{ display: "grid", gap: 6 }}>Username<input name="username" autoComplete="username" required /></label>
        <label style={{ display: "grid", gap: 6 }}>Password<input name="password" type="password" autoComplete="current-password" required /></label>
        {error && <p role="alert" style={{ color: "#ff7a7a", margin: 0 }}>{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}
