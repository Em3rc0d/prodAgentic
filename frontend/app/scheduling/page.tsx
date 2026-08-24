"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PremiumScene } from "@/components/PremiumScene";
import { fetchContentRuns } from "@/lib/api";
import { cancelContentSchedule, scheduleContentRun, ScheduledContentRun } from "@/lib/scheduling";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function tone(status: string) {
  if (status === "PUBLISHED") return "green";
  if (status === "SCHEDULED" || status === "PUBLISHING") return "blue";
  return "purple";
}

export default function SchedulingPage() {
  const [runs, setRuns] = useState<ScheduledContentRun[]>([]);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchContentRuns(100)
      .then((result) => { if (active) setRuns(result.runs as ScheduledContentRun[]); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const queue = useMemo(() => runs.filter((run) => ["APPROVED", "SCHEDULED", "PUBLISHING", "PUBLISHED"].includes(run.status)), [runs]);
  const counts = useMemo(() => ({
    ready: runs.filter((run) => run.status === "APPROVED").length,
    scheduled: runs.filter((run) => run.status === "SCHEDULED").length,
    publishing: runs.filter((run) => run.status === "PUBLISHING").length,
    published: runs.filter((run) => run.status === "PUBLISHED").length,
  }), [runs]);

  async function schedule(run: ScheduledContentRun) {
    const localValue = inputs[run.run_id];
    if (!localValue) return;
    const parsed = new Date(localValue);
    if (Number.isNaN(parsed.getTime())) {
      setError("Choose a valid local date and time.");
      return;
    }
    setActiveId(run.run_id);
    setError(null);
    try {
      const updated = await scheduleContentRun(run.run_id, parsed.toISOString());
      setRuns((current) => current.map((item) => item.run_id === updated.run_id ? updated : item));
      setInputs((current) => ({ ...current, [run.run_id]: "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Schedule failed");
    } finally {
      setActiveId(null);
    }
  }

  async function cancel(run: ScheduledContentRun) {
    setActiveId(run.run_id);
    setError(null);
    try {
      const updated = await cancelContentSchedule(run.run_id);
      setRuns((current) => current.map((item) => item.run_id === updated.run_id ? updated : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setActiveId(null);
    }
  }

  return (
    <main className="premium-page">
      <div className="premium-container">
        <section className="premium-hero">
          <div>
            <div className="premium-kicker">Delivery control</div>
            <h1 className="premium-title">Scheduling</h1>
            <p className="premium-subtitle">Plan exact publication moments for approved bundles. Local time is converted to the exact UTC instant already understood by the backend worker.</p>
            <div className="premium-actions">
              <Link href="/publishing" className="premium-button-secondary">Publishing control</Link>
              <span className="premium-status premium-status--blue">Atomic delivery</span>
            </div>
          </div>
          <PremiumScene variant="scheduling" />
        </section>

        <section className="premium-metrics" aria-label="Scheduling summary">
          <div className="premium-metric"><span className="premium-metric__label">Ready to schedule</span><strong className="premium-metric__value">{counts.ready}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Scheduled</span><strong className="premium-metric__value">{counts.scheduled}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Publishing</span><strong className="premium-metric__value">{counts.publishing}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Published</span><strong className="premium-metric__value">{counts.published}</strong></div>
        </section>

        <section className="premium-panel">
          <header className="premium-panel__header">
            <div><h2>Delivery queue</h2><p>Approved content remains visible before and after a scheduling decision.</p></div>
            <Link href="/library" className="premium-button-secondary">Review library</Link>
          </header>

          <div className="premium-panel__body">
            {error && <div style={{ marginBottom: 14 }} className="premium-status premium-status--red">{error}</div>}
            {loading && <div className="premium-empty"><div><div className="premium-empty__icon">◷</div><h3>Loading delivery queue</h3><p>Reading approved and scheduled ContentRuns.</p></div></div>}
            {!loading && queue.length === 0 && (
              <div className="premium-empty"><div><div className="premium-empty__icon">◴</div><h3>No delivery decisions waiting</h3><p>Approve a ContentRun first. It will appear here ready for an exact publication time.</p><div className="premium-actions" style={{ justifyContent: "center" }}><Link href="/library" className="premium-button">Open library</Link></div></div></div>
            )}

            {!loading && queue.length > 0 && <div style={{ display: "grid", gap: 10 }}>
              {queue.map((run) => (
                <article key={run.run_id} style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(250px, 310px)", gap: 16, alignItems: "center", padding: 16, border: "1px solid rgba(255,255,255,.055)", borderRadius: 16, background: "rgba(255,255,255,.014)" }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
                      <span className={`premium-status premium-status--${tone(run.status)}`}>{run.status}</span>
                      <span style={{ color: "#526074", fontSize: 9 }}>Run {run.run_id.slice(0, 8)}</span>
                    </div>
                    <h3 style={{ margin: 0, color: "#edf3fb", fontSize: 14, letterSpacing: "-.025em" }}>{run.idea}</h3>
                    <p style={{ margin: "5px 0 0", color: "#657489", fontSize: 10, lineHeight: 1.55 }}>{run.topic}</p>
                    {run.schedule && <div style={{ marginTop: 9, color: "#526074", fontSize: 9 }}>Schedule {run.schedule.status} · {formatDate(run.schedule.scheduled_for)}{run.schedule.error_message ? ` · ${run.schedule.error_message}` : ""}</div>}
                  </div>

                  <div style={{ display: "grid", gap: 8 }}>
                    {run.status === "APPROVED" && <>
                      <input className="premium-input" type="datetime-local" aria-label={`Schedule ${run.idea}`} value={inputs[run.run_id] ?? ""} onChange={(event) => setInputs((current) => ({ ...current, [run.run_id]: event.target.value }))} />
                      <button className="premium-button" onClick={() => schedule(run)} disabled={activeId === run.run_id || !inputs[run.run_id]}>{activeId === run.run_id ? "Scheduling…" : "Schedule LinkedIn post"}</button>
                    </>}
                    {run.status === "SCHEDULED" && <button className="premium-button-secondary" onClick={() => cancel(run)} disabled={activeId === run.run_id}>{activeId === run.run_id ? "Cancelling…" : "Cancel schedule"}</button>}
                    <Link href={`/library/${encodeURIComponent(run.run_id)}`} className="premium-button-secondary">Review evidence</Link>
                  </div>
                </article>
              ))}
            </div>}
          </div>
        </section>
      </div>
    </main>
  );
}
