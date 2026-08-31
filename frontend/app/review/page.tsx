"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { fetchContentRuns, type ContentRun } from "@/lib/api";
import type { GroundingContentRun } from "@/lib/grounding-api";

function groundingState(run: ContentRun): { label: string; tone: string } {
  const value = run as GroundingContentRun;
  if (value.grounding_review?.decision === "VERIFIED") return { label: "Grounding verified", tone: "green" };
  if (value.grounding_review?.decision === "REJECTED") return { label: "Grounding rejected", tone: "red" };
  if (value.grounding_gate?.decision === "BLOCK") return { label: "Grounding blocked", tone: "red" };
  if (value.grounding_gate?.decision === "PASS") return { label: "Awaiting human verification", tone: "amber" };
  if (value.claim_extraction_review?.decision === "VERIFIED_COMPLETE") return { label: "Claims verified · match evidence", tone: "blue" };
  if (value.claim_extraction) return { label: "Review claim completeness", tone: "purple" };
  return { label: "Extract claims", tone: "amber" };
}

export default function ReviewQueuePage() {
  const [runs, setRuns] = useState<ContentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchContentRuns(100)
      .then((result) => { if (active) setRuns(result.runs); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const queue = useMemo(
    () => runs.filter((run) => run.status === "READY_FOR_REVIEW"),
    [runs],
  );
  const verified = queue.filter((run) => (run as GroundingContentRun).grounding_review?.decision === "VERIFIED").length;
  const blocked = queue.filter((run) => (run as GroundingContentRun).grounding_gate?.decision === "BLOCK").length;

  return (
    <main className="premium-page">
      <div className="premium-container">
        <section className="premium-hero">
          <div>
            <div className="premium-kicker">Trust cockpit</div>
            <h1 className="premium-title">Human review center</h1>
            <p className="premium-subtitle">
              Inspect extracted claims, verify completeness, run server-owned semantic Grounding, and explicitly retain human authority before approval.
            </p>
          </div>
        </section>

        <section className="premium-metrics" aria-label="Review queue summary">
          <div className="premium-metric"><span className="premium-metric__label">Ready for review</span><strong className="premium-metric__value">{queue.length}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Grounding verified</span><strong className="premium-metric__value">{verified}</strong></div>
          <div className="premium-metric"><span className="premium-metric__label">Policy blocked</span><strong className="premium-metric__value">{blocked}</strong></div>
        </section>

        <section className="premium-panel">
          <header className="premium-panel__header">
            <div>
              <h2>Review queue</h2>
              <p>No model can mark extraction complete, verify Grounding, or approve publication on your behalf.</p>
            </div>
          </header>
          <div className="premium-panel__body">
            {error && <div className="premium-empty"><div><h3>Review queue unavailable</h3><p>{error}</p></div></div>}
            {loading && !error && <div className="premium-empty"><div><h3>Loading review state</h3><p>Reading persisted ContentRuns and their current trust material.</p></div></div>}
            {!loading && !error && queue.length === 0 && (
              <div className="premium-empty"><div><h3>No runs waiting for review</h3><p>Create an evidence-fed content run and it will appear here when the text reaches READY_FOR_REVIEW.</p><div className="premium-actions" style={{ justifyContent: "center" }}><Link href="/" className="premium-button">Create evidence-fed content</Link></div></div></div>
            )}
            {!loading && !error && queue.length > 0 && (
              <div style={{ display: "grid", gap: 12 }}>
                {queue.map((run) => {
                  const state = groundingState(run);
                  const grounded = run as GroundingContentRun;
                  return (
                    <article key={run.run_id} style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 16, background: "var(--surface-active)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
                            <span className={`premium-status premium-status--${state.tone}`}>{state.label}</span>
                            <span style={{ color: "var(--text-3)", fontSize: 12 }}>{run.style}</span>
                            <span style={{ color: "var(--text-3)", fontSize: 12 }}>{grounded.generation_source_packet ? "Evidence-fed" : "No generation evidence"}</span>
                          </div>
                          <strong style={{ display: "block", fontSize: 16, marginBottom: 5 }}>{run.idea}</strong>
                          <p style={{ margin: 0, color: "var(--text-2)", lineHeight: 1.45 }}>{run.topic}</p>
                        </div>
                        <Link href={`/review/${encodeURIComponent(run.run_id)}`} className="premium-button-secondary">Open trust cockpit</Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
