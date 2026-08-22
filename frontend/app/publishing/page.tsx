"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchContentRuns } from "@/lib/api";
import {
  connectLinkedIn,
  disconnectLinkedIn,
  fetchLinkedInPublisherStatus,
  LinkedInPublisherStatus,
  PublicationSnapshot,
  PublishableContentRun,
  publishContentRun,
} from "@/lib/publishing";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function PublishingPage() {
  const [runs, setRuns] = useState<PublishableContentRun[]>([]);
  const [publisher, setPublisher] = useState<LinkedInPublisherStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [connectionBusy, setConnectionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const [runResult, publisherResult] = await Promise.all([fetchContentRuns(100), fetchLinkedInPublisherStatus()]);
    setRuns(runResult.runs as PublishableContentRun[]);
    setPublisher(publisherResult);
  }

  useEffect(() => {
    let active = true;
    Promise.all([fetchContentRuns(100), fetchLinkedInPublisherStatus()])
      .then(([runResult, publisherResult]) => {
        if (!active) return;
        setRuns(runResult.runs as PublishableContentRun[]);
        setPublisher(publisherResult);
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const queue = useMemo(
    () => runs.filter((run) => ["APPROVED", "PUBLISHING", "PUBLISHED"].includes(run.status)),
    [runs]
  );

  async function startLinkedInConnection() {
    setConnectionBusy(true);
    setError(null);
    try {
      await connectLinkedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "LinkedIn connection failed");
      setConnectionBusy(false);
    }
  }

  async function disconnect() {
    setConnectionBusy(true);
    setError(null);
    try {
      await disconnectLinkedIn();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "LinkedIn disconnect failed");
    } finally {
      setConnectionBusy(false);
    }
  }

  async function publish(run: PublishableContentRun) {
    setActiveId(run.run_id);
    setError(null);
    try {
      const updated = await publishContentRun(run.run_id);
      setRuns((current) => current.map((item) => item.run_id === updated.run_id ? updated : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Publish failed");
      await reload().catch(() => undefined);
    } finally {
      setActiveId(null);
    }
  }

  const card = { border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 18 } as const;
  const connected = publisher?.connected === true;

  return (
    <main style={{ height: "100vh", overflowY: "auto", background: "var(--bg-0)", color: "var(--text-1)", padding: "44px 24px 100px" }}>
      <div style={{ maxWidth: 1050, margin: "0 auto" }}>
        <header style={{ marginBottom: 26 }}>
          <p style={{ margin: 0, color: "var(--text-3)", fontSize: 12, letterSpacing: ".08em" }}>DISTRIBUTION</p>
          <h1 style={{ margin: "6px 0 8px", fontSize: 32 }}>LinkedIn Publishing</h1>
          <p style={{ margin: 0, color: "var(--text-2)", maxWidth: 760 }}>Connect your LinkedIn member account, then publish only immutable approved bundles. The publisher never reads mutable draft fields.</p>
        </header>

        <section style={{ ...card, marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 12, alignItems: "center", minWidth: 0 }}>
              {publisher?.picture_url && <img src={publisher.picture_url} alt="LinkedIn profile" width={42} height={42} style={{ borderRadius: "50%", objectFit: "cover" }} />}
              <div>
                <strong>LinkedIn account</strong>
                <div style={{ color: "var(--text-3)", marginTop: 5, fontSize: 12 }}>
                  {connected
                    ? `${publisher?.display_name || publisher?.author_urn} · API ${publisher?.api_version}`
                    : publisher?.status === "RECONNECT_REQUIRED"
                      ? `Connection expired${publisher?.expires_at ? ` · ${formatDate(publisher.expires_at)}` : ""}`
                      : publisher?.reason ?? "No LinkedIn account connected"}
                </div>
                {connected && publisher?.expires_at && <div style={{ color: "var(--text-3)", marginTop: 4, fontSize: 11 }}>Token expires {formatDate(publisher.expires_at)}</div>}
              </div>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span style={{ color: connected ? "var(--success)" : "var(--warning)", fontSize: 12 }}>
                {connected ? "CONNECTED" : publisher?.status === "RECONNECT_REQUIRED" ? "RECONNECT REQUIRED" : "NOT CONNECTED"}
              </span>
              {connected ? (
                <button onClick={disconnect} disabled={connectionBusy} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px", background: "transparent", color: "var(--text-2)", cursor: connectionBusy ? "not-allowed" : "pointer" }}>
                  {connectionBusy ? "Disconnecting…" : "Disconnect"}
                </button>
              ) : (
                <button onClick={startLinkedInConnection} disabled={connectionBusy || publisher?.configured === false} style={{ border: "1px solid var(--border-active)", borderRadius: 8, padding: "9px 12px", background: "var(--surface-active)", color: "var(--text-1)", cursor: connectionBusy ? "not-allowed" : "pointer" }}>
                  {connectionBusy ? "Connecting…" : publisher?.status === "RECONNECT_REQUIRED" ? "Reconnect LinkedIn" : "Connect LinkedIn"}
                </button>
              )}
            </div>
          </div>
        </section>

        {error && <div style={{ ...card, marginBottom: 18, color: "#fca5a5" }}>{error}</div>}
        {loading && <p style={{ color: "var(--text-2)" }}>Loading publication queue…</p>}
        {!loading && queue.length === 0 && <div style={card}>No approved or published ContentRuns yet.</div>}

        <div style={{ display: "grid", gap: 12 }}>
          {queue.map((run) => {
            const publication = (run.publication ?? null) as PublicationSnapshot | null;
            const canPublish = run.status === "APPROVED" && connected && activeId !== run.run_id;
            return (
              <article key={run.run_id} style={card}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 18 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
                      <span style={{ border: "1px solid var(--border)", borderRadius: 999, padding: "4px 8px", fontSize: 11 }}>{run.status}</span>
                      <span style={{ color: "var(--text-3)", fontSize: 11 }}>Run {run.run_id.slice(0, 8)}</span>
                    </div>
                    <h2 style={{ margin: "0 0 5px", fontSize: 18 }}>{run.idea}</h2>
                    <p style={{ margin: 0, color: "var(--text-2)", fontSize: 13 }}>{run.topic}</p>
                    {run.approval && <div style={{ marginTop: 12, color: "var(--text-3)", fontSize: 11 }}>Approved {formatDate(run.approval.approved_at)} · bundle {run.approval.bundle_sha256.slice(0, 14)}… · {run.approval.include_visual ? "text + visual" : "text only"}</div>}
                    {publication && <div style={{ marginTop: 10, color: "var(--text-3)", fontSize: 11 }}>Publication: {publication.status} · started {formatDate(publication.started_at)}{publication.external_post_urn ? ` · ${publication.external_post_urn}` : ""}{publication.error_message ? ` · ${publication.error_message}` : ""}</div>}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "stretch" }}>
                    <Link href={`/library/${encodeURIComponent(run.run_id)}`} style={{ color: "var(--text-2)", textDecoration: "none", border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px", textAlign: "center", fontSize: 12 }}>Review evidence</Link>
                    {run.status === "APPROVED" && <button onClick={() => publish(run)} disabled={!canPublish} style={{ border: "1px solid var(--border-active)", borderRadius: 8, padding: "9px 12px", background: "var(--surface-active)", color: "var(--text-1)", cursor: canPublish ? "pointer" : "not-allowed", opacity: canPublish ? 1 : .55 }}>{activeId === run.run_id ? "Publishing…" : connected ? "Publish to LinkedIn" : "Connect LinkedIn first"}</button>}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </main>
  );
}
