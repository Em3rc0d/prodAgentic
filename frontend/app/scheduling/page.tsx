"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchContentRuns } from "@/lib/api";
import { cancelContentSchedule, scheduleContentRun, ScheduledContentRun } from "@/lib/scheduling";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
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

  const queue = useMemo(
    () => runs.filter((run) => ["APPROVED", "SCHEDULED", "PUBLISHING", "PUBLISHED"].includes(run.status)),
    [runs]
  );

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

  const card = { border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 18 } as const;

  return (
    <main style={{ height: "100vh", overflowY: "auto", background: "var(--bg-0)", color: "var(--text-1)", padding: "44px 24px 100px" }}>
      <div style={{ maxWidth: 1050, margin: "0 auto" }}>
        <header style={{ marginBottom: 26 }}>
          <p style={{ margin: 0, color: "var(--text-3)", fontSize: 12, letterSpacing: ".08em" }}>DELIVERY CONTROL</p>
          <h1 style={{ margin: "6px 0 8px", fontSize: 32 }}>Scheduling</h1>
          <p style={{ margin: 0, color: "var(--text-2)", maxWidth: 780 }}>Choose a local date/time. The browser converts it to an offset-aware UTC instant; the backend stores that exact instant and the worker atomically claims due schedules.</p>
        </header>

        {error && <div style={{ ...card, marginBottom: 18, color: "#fca5a5" }}>{error}</div>}
        {loading && <p style={{ color: "var(--text-2)" }}>Loading delivery queue…</p>}
        {!loading && queue.length === 0 && <div style={card}>No approved or scheduled content yet.</div>}

        <div style={{ display: "grid", gap: 12 }}>
          {queue.map((run) => (
            <article key={run.run_id} style={card}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr minmax(260px, auto)", gap: 18, alignItems: "center" }}>
                <div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 7 }}><span style={{ border: "1px solid var(--border)", borderRadius: 999, padding: "4px 8px", fontSize: 11 }}>{run.status}</span><span style={{ color: "var(--text-3)", fontSize: 11 }}>Run {run.run_id.slice(0, 8)}</span></div>
                  <h2 style={{ margin: "0 0 5px", fontSize: 18 }}>{run.idea}</h2>
                  <p style={{ margin: 0, color: "var(--text-2)", fontSize: 13 }}>{run.topic}</p>
                  {run.schedule && <div style={{ marginTop: 10, color: "var(--text-3)", fontSize: 11 }}>Schedule {run.schedule.status} · {formatDate(run.schedule.scheduled_for)}{run.schedule.error_message ? ` · ${run.schedule.error_message}` : ""}</div>}
                </div>

                <div style={{ display: "grid", gap: 8 }}>
                  {run.status === "APPROVED" && (
                    <>
                      <input type="datetime-local" aria-label={`Schedule ${run.idea}`} value={inputs[run.run_id] ?? ""} onChange={(event) => setInputs((current) => ({ ...current, [run.run_id]: event.target.value }))} style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface-active)", color: "var(--text-1)", padding: "9px 10px" }} />
                      <button onClick={() => schedule(run)} disabled={activeId === run.run_id || !inputs[run.run_id]} style={{ border: "1px solid var(--border-active)", borderRadius: 8, padding: "9px 12px", background: "var(--surface-active)", color: "var(--text-1)", cursor: "pointer", opacity: activeId === run.run_id || !inputs[run.run_id] ? .55 : 1 }}>{activeId === run.run_id ? "Scheduling…" : "Schedule LinkedIn post"}</button>
                    </>
                  )}
                  {run.status === "SCHEDULED" && <button onClick={() => cancel(run)} disabled={activeId === run.run_id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px", background: "transparent", color: "var(--text-1)", cursor: "pointer" }}>{activeId === run.run_id ? "Cancelling…" : "Cancel schedule"}</button>}
                  <Link href={`/library/${encodeURIComponent(run.run_id)}`} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px", color: "var(--text-2)", textDecoration: "none", textAlign: "center", fontSize: 12 }}>Review evidence</Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
