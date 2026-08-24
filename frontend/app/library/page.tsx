"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PremiumScene } from "@/components/PremiumScene";
import { ContentRun, ContentRunStatus, fetchContentRuns } from "@/lib/api";

const STATUS_ORDER: ContentRunStatus[] = ["READY_FOR_REVIEW", "TEXT_READY", "GENERATING", "FAILED", "APPROVED", "SCHEDULED", "PUBLISHING", "PUBLISHED", "CANCELLED", "ARCHIVED"];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function statusLabel(status: ContentRunStatus) {
  return status.replaceAll("_", " ");
}

function statusTone(status: ContentRunStatus) {
  if (status === "APPROVED" || status === "PUBLISHED") return "green";
  if (status === "SCHEDULED" || status === "PUBLISHING") return "blue";
  if (status === "FAILED" || status === "CANCELLED") return "red";
  if (status === "READY_FOR_REVIEW") return "purple";
  return "amber";
}

export default function ContentLibraryPage() {
  const [runs, setRuns] = useState<ContentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ContentRunStatus | "ALL">("ALL");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    fetchContentRuns(100)
      .then((result) => { if (active) setRuns(result.runs); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const visibleRuns = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return runs.filter((run) => {
      if (filter !== "ALL" && run.status !== filter) return false;
      if (!normalized) return true;
      return [run.idea, run.topic, run.style, run.resolved_target_language ?? ""].some((value) => value.toLowerCase().includes(normalized));
    });
  }, [filter, query, runs]);

  const availableStatuses = useMemo(() => STATUS_ORDER.filter((status) => runs.some((run) => run.status === status)), [runs]);
  const counts = useMemo(() => ({
    approved: runs.filter((run) => run.status === "APPROVED").length,
    scheduled: runs.filter((run) => run.status === "SCHEDULED").length,
    published: runs.filter((run) => run.status === "PUBLISHED").length,
  }), [runs]);

  return (
    <main className="premium-page">
      <div className="premium-container">
        <section className="premium-hero">
          <div>
            <div className="premium-kicker">Content memory</div>
            <h1 className="premium-title">Content library</h1>
            <p className="premium-subtitle">Every persisted ContentRun remains traceable from the original idea through approval, scheduling and publication evidence.</p>
            <div className="premium-actions">
              <Link href="/" className="premium-button">Create new content</Link>
              <span className="premium-status premium-status--green">Durable lineage</span>
            </div>
          </div>
          <PremiumScene variant="library" />
        </section>

        <section className="premium-metrics" aria-label="Library summary">
          <div className="premium-metric"><span className="premium-metric__label">Total runs</span><strong className="premium-metric__value">{runs.length}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Approved</span><strong className="premium-metric__value">{counts.approved}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Scheduled</span><strong className="premium-metric__value">{counts.scheduled}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Published</span><strong className="premium-metric__value">{counts.published}</strong></div>
        </section>

        <section className="premium-panel">
          <header className="premium-panel__header">
            <div><h2>Run archive</h2><p>Search and filter persisted content without changing its evidence.</p></div>
            <input className="premium-input" style={{ maxWidth: 290 }} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search content runs…" aria-label="Search content runs" />
          </header>

          <div className="premium-panel__body">
            <div className="premium-filterbar">
              <button className={`premium-chip${filter === "ALL" ? " premium-chip--active" : ""}`} onClick={() => setFilter("ALL")}>All · {runs.length}</button>
              {availableStatuses.map((status) => (
                <button key={status} className={`premium-chip${filter === status ? " premium-chip--active" : ""}`} onClick={() => setFilter(status)}>{statusLabel(status)} · {runs.filter((run) => run.status === status).length}</button>
              ))}
            </div>

            {error && <div className="premium-empty"><div><div className="premium-empty__icon">!</div><h3>Library unavailable</h3><p>{error}</p></div></div>}
            {loading && !error && <div className="premium-empty"><div><div className="premium-empty__icon">⌁</div><h3>Loading durable runs</h3><p>Reading the persisted ContentRun archive.</p></div></div>}

            {!loading && !error && visibleRuns.length === 0 && (
              <div className="premium-empty"><div><div className="premium-empty__icon">◇</div><h3>{runs.length === 0 ? "Your archive starts with the first run" : "No runs match this view"}</h3><p>{runs.length === 0 ? "Generate content and prodAgentic will preserve its lineage here automatically." : "Change the filter or search query to reveal other ContentRuns."}</p>{runs.length === 0 && <div className="premium-actions" style={{ justifyContent: "center" }}><Link href="/" className="premium-button">Create content</Link></div>}</div></div>
            )}

            {!loading && !error && visibleRuns.length > 0 && (
              <div style={{ overflowX: "auto" }}>
                <table className="premium-table">
                  <thead><tr><th>Status</th><th>Content</th><th>Profile context</th><th>Updated</th><th aria-label="Actions" /></tr></thead>
                  <tbody>
                    {visibleRuns.map((run) => (
                      <tr key={run.run_id}>
                        <td><span className={`premium-status premium-status--${statusTone(run.status)}`}>{statusLabel(run.status)}</span></td>
                        <td><Link href={`/library/${encodeURIComponent(run.run_id)}`} style={{ color: "#e7edf7", textDecoration: "none", fontWeight: 650 }}>{run.idea}</Link><div style={{ marginTop: 4, color: "#627086", maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{run.topic}</div></td>
                        <td><div>{run.style}</div><div style={{ color: "#536075", marginTop: 3 }}>{(run.resolved_target_language ?? "—").toUpperCase()}</div></td>
                        <td>{formatDate(run.updated_at)}</td>
                        <td><Link href={`/library/${encodeURIComponent(run.run_id)}`} className="premium-button-secondary">Open</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
