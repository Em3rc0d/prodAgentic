"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PremiumScene } from "@/components/PremiumScene";
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

function initials(name?: string | null) {
  if (!name) return "LI";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return `${parts[0]?.[0] ?? "L"}${parts.length > 1 ? parts[parts.length - 1][0] : "I"}`.toUpperCase();
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
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const queue = useMemo(() => runs.filter((run) => ["APPROVED", "PUBLISHING", "PUBLISHED"].includes(run.status)), [runs]);
  const readyCount = useMemo(() => queue.filter((run) => run.status === "APPROVED").length, [queue]);
  const publishedCount = useMemo(() => queue.filter((run) => run.status === "PUBLISHED").length, [queue]);
  const connected = publisher?.connected === true;

  async function startLinkedInConnection() {
    setConnectionBusy(true);
    setError(null);
    try {
      const authorizationUrl = await connectLinkedIn();
      window.location.assign(authorizationUrl);
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
    } finally { setConnectionBusy(false); }
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
    } finally { setActiveId(null); }
  }

  const statusText = connected ? "Connected" : publisher?.status === "RECONNECT_REQUIRED" ? "Reconnect required" : "Not connected";

  return (
    <main className="premium-page">
      <div className="premium-container">
        <section className="premium-hero">
          <div>
            <div className="premium-kicker">Distribution control</div>
            <h1 className="premium-title">LinkedIn publishing</h1>
            <p className="premium-subtitle">Connect once. Approve deliberately. Publish exactly what was reviewed—never a mutable draft.</p>
            <div className="premium-actions">
              <span className={`premium-status premium-status--${connected ? "green" : "amber"}`}>{statusText}</span>
              <span className="premium-status premium-status--purple">Immutable bundle authority</span>
            </div>
          </div>
          <PremiumScene variant="publishing" />
        </section>

        <section className="premium-metrics" aria-label="Publishing summary">
          <div className="premium-metric"><span className="premium-metric__label">Identity</span><strong className="premium-metric__value" style={{ fontSize: 15, marginTop: 13 }}>{connected ? "Connected" : "Offline"}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Ready to publish</span><strong className="premium-metric__value">{readyCount}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Published</span><strong className="premium-metric__value">{publishedCount}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Provider</span><strong className="premium-metric__value" style={{ fontSize: 15, marginTop: 13 }}>LinkedIn {publisher?.api_version || "—"}</strong></div>
        </section>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.4fr) minmax(290px,.6fr)", gap: 14, marginBottom: 18 }}>
          <section className="premium-panel">
            <header className="premium-panel__header"><div><h2>Publishing identity</h2><p>Member authority used only after explicit ContentRun approval.</p></div><span className={`premium-status premium-status--${connected ? "green" : "amber"}`}>{statusText}</span></header>
            <div className="premium-panel__body">
              <div style={{ display: "grid", gridTemplateColumns: "58px minmax(0,1fr)", gap: 14, alignItems: "center" }}>
                <div style={{ width: 58, height: 58, display: "grid", placeItems: "center", border: "1px solid rgba(139,92,246,.24)", borderRadius: 18, color: "#f4f0ff", background: "linear-gradient(145deg, rgba(151,112,255,.36), rgba(53,92,215,.18))", boxShadow: "0 16px 34px rgba(58,39,131,.24), inset 0 1px 0 rgba(255,255,255,.08)", fontSize: 14, fontWeight: 750 }}>{initials(publisher?.display_name)}</div>
                <div style={{ minWidth: 0 }}><h3 style={{ margin: 0, color: "#edf3fb", fontSize: 16, letterSpacing: "-.03em" }}>{connected ? publisher?.display_name || "LinkedIn member" : "LinkedIn member account"}</h3><p style={{ margin: "5px 0 0", color: "#657489", fontSize: 10, lineHeight: 1.55 }}>{connected ? "Personal publishing authority is active." : publisher?.reason || "Connect a member account before publishing."}</p></div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr)) auto", gap: 12, alignItems: "end", marginTop: 18, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,.055)" }}>
                <div><span className="premium-metric__label">Token validity</span><div style={{ marginTop: 6, color: "#aab6c6", fontSize: 10 }}>{connected && publisher?.expires_at ? `Until ${formatDate(publisher.expires_at)}` : "No active token"}</div></div>
                <div><span className="premium-metric__label">Provider contract</span><div style={{ marginTop: 6, color: "#aab6c6", fontSize: 10 }}>LinkedIn API {publisher?.api_version || "—"}</div></div>
                {connected ? <button className="premium-button-secondary" onClick={disconnect} disabled={connectionBusy}>{connectionBusy ? "Disconnecting…" : "Disconnect"}</button> : <button className="premium-button" onClick={startLinkedInConnection} disabled={connectionBusy || publisher?.configured === false}>{connectionBusy ? "Connecting…" : publisher?.status === "RECONNECT_REQUIRED" ? "Reconnect LinkedIn" : "Connect LinkedIn"}</button>}
              </div>
            </div>
          </section>

          <aside className="premium-panel">
            <header className="premium-panel__header"><div><h2>Publishing guardrail</h2><p>Connection never equals permission to post.</p></div></header>
            <div className="premium-panel__body" style={{ display: "grid", gap: 10 }}>
              {[
                ["01", "Connect identity", connected ? "Member authority verified" : "OAuth connection required", connected],
                ["02", "Approve content", readyCount > 0 ? `${readyCount} approved bundle${readyCount === 1 ? "" : "s"}` : "Human approval is required", readyCount > 0],
                ["03", "Publish exact bundle", "External receipt persists after success", false],
              ].map(([index, title, copy, done]) => <div key={String(index)} style={{ display: "grid", gridTemplateColumns: "30px 1fr", gap: 10, alignItems: "center", padding: 10, border: "1px solid rgba(255,255,255,.045)", borderRadius: 12, background: "rgba(255,255,255,.012)" }}><span style={{ width: 30, height: 30, display: "grid", placeItems: "center", borderRadius: 9, color: done ? "#58d69d" : "#758399", background: done ? "rgba(43,184,121,.07)" : "rgba(255,255,255,.025)", fontSize: 9, fontWeight: 750 }}>{done ? "✓" : index}</span><div><div style={{ color: "#c1cad6", fontSize: 10, fontWeight: 650 }}>{title}</div><div style={{ marginTop: 3, color: "#526074", fontSize: 8, lineHeight: 1.45 }}>{copy}</div></div></div>)}
            </div>
          </aside>
        </div>

        {error && <div style={{ marginBottom: 14 }} className="premium-status premium-status--red">{error}</div>}

        <section className="premium-panel">
          <header className="premium-panel__header"><div><h2>Publication queue</h2><p>Approved, in-flight and published ContentRuns appear here.</p></div><Link href="/library" className="premium-button-secondary">Review library</Link></header>
          <div className="premium-panel__body">
            {loading && <div className="premium-empty"><div><div className="premium-empty__icon">⌁</div><h3>Loading publication queue</h3><p>Reading approved publication authority.</p></div></div>}
            {!loading && queue.length === 0 && <div className="premium-empty"><div><div className="premium-empty__icon">➤</div><h3>Your connection is ready. The queue is intentionally empty.</h3><p>Create a ContentRun, review the final text and visual, then approve it. Only that immutable approval bundle becomes publishable.</p><div className="premium-actions" style={{ justifyContent: "center" }}><Link href="/" className="premium-button">Create content</Link><Link href="/library" className="premium-button-secondary">Open library</Link></div></div></div>}

            {!loading && queue.length > 0 && <div style={{ display: "grid", gap: 10 }}>{queue.map((run) => {
              const publication = (run.publication ?? null) as PublicationSnapshot | null;
              const canPublish = run.status === "APPROVED" && connected && activeId !== run.run_id;
              return <article key={run.run_id} style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: 18, padding: 16, border: "1px solid rgba(255,255,255,.055)", borderRadius: 15, background: "rgba(255,255,255,.014)" }}>
                <div style={{ minWidth: 0 }}><div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}><span className={`premium-status premium-status--${run.status === "PUBLISHED" ? "green" : run.status === "PUBLISHING" ? "blue" : "purple"}`}>{run.status}</span><span style={{ color: "#526074", fontSize: 8 }}>RUN {run.run_id.slice(0, 8)}</span></div><h3 style={{ margin: 0, color: "#e7edf7", fontSize: 14 }}>{run.idea}</h3><p style={{ margin: "5px 0 0", color: "#657489", fontSize: 10 }}>{run.topic}</p>{run.approval && <div style={{ marginTop: 9, color: "#526074", fontSize: 8 }}>Approved {formatDate(run.approval.approved_at)} · bundle {run.approval.bundle_sha256.slice(0, 14)}… · {run.approval.include_visual ? "text + visual" : "text only"}</div>}{publication && <div style={{ marginTop: 6, color: "#526074", fontSize: 8 }}>Publication {publication.status} · started {formatDate(publication.started_at)}{publication.external_post_urn ? ` · ${publication.external_post_urn}` : ""}{publication.error_message ? ` · ${publication.error_message}` : ""}</div>}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 7, justifyContent: "center" }}><Link href={`/library/${encodeURIComponent(run.run_id)}`} className="premium-button-secondary">Review evidence</Link>{run.status === "APPROVED" && <button className="premium-button" onClick={() => publish(run)} disabled={!canPublish}>{activeId === run.run_id ? "Publishing…" : connected ? "Publish to LinkedIn" : "Connect LinkedIn first"}</button>}</div>
              </article>;
            })}</div>}
          </div>
        </section>
      </div>
    </main>
  );
}
