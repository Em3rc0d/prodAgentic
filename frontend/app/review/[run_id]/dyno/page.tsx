"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchContentRun, resolveBackendAssetUrl, type ContentRun } from "@/lib/api";
import {
  fetchDynoReport,
  submitDynoReview,
  type DynoReport,
  type EditorialVerdict,
  type HumanEditorialReviewInput,
} from "@/lib/dyno-api";

type ScoreKey =
  | "topic_fidelity"
  | "pov_strength"
  | "human_voice"
  | "usefulness"
  | "visual_message_fit"
  | "publish_readiness";

const SCORE_FIELDS: Array<{ key: ScoreKey; label: string; hint: string }> = [
  { key: "topic_fidelity", label: "Topic fidelity", hint: "Does the final piece actually answer the intended topic?" },
  { key: "pov_strength", label: "POV strength", hint: "Is there a defensible point of view rather than generic explanation?" },
  { key: "human_voice", label: "Human voice", hint: "Does it read like a person with judgement, not a generated manual?" },
  { key: "usefulness", label: "Usefulness", hint: "Does the reader leave with a concrete model, decision or technique?" },
  { key: "visual_message_fit", label: "Visual message fit", hint: "Does the visual sharpen the same idea instead of decorating it?" },
  { key: "publish_readiness", label: "Publish readiness", hint: "Would you publish this exact text + visual without another rewrite?" },
];

const VERDICTS: Array<{ value: EditorialVerdict; label: string }> = [
  { value: "DO_NOT_PUBLISH", label: "Do not publish" },
  { value: "PUBLISHABLE", label: "Publishable" },
  { value: "STRONG", label: "Strong" },
  { value: "EXCELLENT", label: "Excellent" },
  { value: "WOULD_PUBLISH_NOW", label: "Would publish now" },
];

const DEFAULT_SCORES: Record<ScoreKey, number> = {
  topic_fidelity: 80,
  pov_strength: 80,
  human_voice: 80,
  usefulness: 80,
  visual_message_fit: 80,
  publish_readiness: 80,
};

function tone(value: string) {
  if (["SIGNED_PASS", "PASS", "WOULD_PUBLISH_NOW"].includes(value)) return "green";
  if (["TRUST_FAIL", "FAIL", "DO_NOT_PUBLISH"].includes(value)) return "red";
  if (["UNSIGNED", "NOT_MEASURED", "PUBLISHABLE"].includes(value)) return "amber";
  return "purple";
}

function shortDigest(value?: string | null) {
  if (!value) return "—";
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

export default function ProductDynoPage() {
  const params = useParams<{ run_id: string }>();
  const runId = decodeURIComponent(params.run_id);
  const [run, setRun] = useState<ContentRun | null>(null);
  const [report, setReport] = useState<DynoReport | null>(null);
  const [scores, setScores] = useState<Record<ScoreKey, number>>(DEFAULT_SCORES);
  const [verdict, setVerdict] = useState<EditorialVerdict>("DO_NOT_PUBLISH");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextRun, nextReport] = await Promise.all([
      fetchContentRun(runId),
      fetchDynoReport(runId),
    ]);
    setRun(nextRun);
    setReport(nextReport);
    if (nextReport.human_review) {
      const review = nextReport.human_review;
      setScores({
        topic_fidelity: Math.round(review.topic_fidelity * 100),
        pov_strength: Math.round(review.pov_strength * 100),
        human_voice: Math.round(review.human_voice * 100),
        usefulness: Math.round(review.usefulness * 100),
        visual_message_fit: Math.round(review.visual_message_fit * 100),
        publish_readiness: Math.round(review.publish_readiness * 100),
      });
      setVerdict(review.verdict);
      setNotes(review.notes.join("\n"));
    }
  }, [runId]);

  useEffect(() => {
    let active = true;
    Promise.all([fetchContentRun(runId), fetchDynoReport(runId)])
      .then(([nextRun, nextReport]) => {
        if (!active) return;
        setRun(nextRun);
        setReport(nextReport);
        if (nextReport.human_review) {
          const review = nextReport.human_review;
          setScores({
            topic_fidelity: Math.round(review.topic_fidelity * 100),
            pov_strength: Math.round(review.pov_strength * 100),
            human_voice: Math.round(review.human_voice * 100),
            usefulness: Math.round(review.usefulness * 100),
            visual_message_fit: Math.round(review.visual_message_fit * 100),
            publish_readiness: Math.round(review.publish_readiness * 100),
          });
          setVerdict(review.verdict);
          setNotes(review.notes.join("\n"));
        }
      })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [runId]);

  const visualUrl = resolveBackendAssetUrl(run?.visual_render?.asset_url);
  const canReview = Boolean(
    run?.status === "READY_FOR_REVIEW"
    && run.final_content
    && run.visual_render?.status === "READY"
    && run.visual_render.asset_sha256,
  );
  const highLosses = useMemo(
    () => report?.drivetrain_losses.filter((loss) => loss.severity === "HIGH") ?? [],
    [report],
  );

  async function saveReview() {
    if (!canReview) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    const input: HumanEditorialReviewInput = {
      topic_fidelity: scores.topic_fidelity / 100,
      pov_strength: scores.pov_strength / 100,
      human_voice: scores.human_voice / 100,
      usefulness: scores.usefulness / 100,
      visual_message_fit: scores.visual_message_fit / 100,
      publish_readiness: scores.publish_readiness / 100,
      verdict,
      notes: notes.split("\n").map((item) => item.trim()).filter(Boolean).slice(0, 12),
    };
    try {
      await submitDynoReview(runId, input);
      await refresh();
      setMessage("Editorial dyno review saved and rebound to the exact current text + visual.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dyno review failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className="premium-page"><div className="premium-container"><div className="premium-empty"><div><h3>Loading product dyno</h3><p>Reading the exact final asset and current drivetrain state.</p></div></div></div></main>;
  }

  if (!run || !report) {
    return <main className="premium-page"><div className="premium-container"><Link href="/review">← Review center</Link><div className="premium-empty"><div><h3>Dyno unavailable</h3><p>{error ?? "The requested ContentRun could not be measured."}</p></div></div></div></main>;
  }

  return (
    <main className="premium-page">
      <div className="premium-container">
        <header style={{ marginBottom: 24 }}>
          <Link href={`/review/${encodeURIComponent(run.run_id)}`} style={{ color: "var(--text-2)", textDecoration: "none", fontSize: 13 }}>← Trust cockpit</Link>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 18, alignItems: "flex-start", marginTop: 14, flexWrap: "wrap" }}>
            <div style={{ maxWidth: 760 }}>
              <div className="premium-kicker">Product dyno · {report.dyno_version}</div>
              <h1 className="premium-title" style={{ fontSize: 32 }}>Wheel HP editorial</h1>
              <p className="premium-subtitle">Measure the final text + visual a person would actually publish. Trust and editorial value remain separate; there is deliberately no compensating combined score.</p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
              <span className={`premium-status premium-status--${tone(report.signature)}`}>{report.signature.replaceAll("_", " ")}</span>
              <span className={`premium-status premium-status--${tone(report.trust_at_wheels.status)}`}>TRUST · {report.trust_at_wheels.status.replaceAll("_", " ")}</span>
              <span className={`premium-status premium-status--${highLosses.length === 0 ? "green" : "amber"}`}>{highLosses.length} HIGH LOSS{highLosses.length === 1 ? "" : "ES"}</span>
            </div>
          </div>
        </header>

        {(error || message) && (
          <div style={{ marginBottom: 18, border: "1px solid var(--border)", borderRadius: 10, padding: 12, background: "var(--surface)", color: error ? "#ffb4b4" : "var(--text-2)" }}>
            {error ?? message}
          </div>
        )}

        <section style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.25fr) minmax(300px, .75fr)", gap: 18, marginBottom: 18 }}>
          <article className="premium-panel">
            <header className="premium-panel__header"><div><h2>Exact final text</h2><p>Human judgement is SHA-bound to this revision.</p></div></header>
            <div className="premium-panel__body">
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.65, color: "var(--text-1)" }}>{run.final_content || "No final content"}</div>
              <p style={{ margin: "14px 0 0", color: "var(--text-3)", fontSize: 11, fontFamily: "monospace" }}>content · {shortDigest(report.final_content_sha256)}</p>
            </div>
          </article>

          <article className="premium-panel">
            <header className="premium-panel__header"><div><h2>Exact final visual</h2><p>The visual is part of the measured editorial asset.</p></div></header>
            <div className="premium-panel__body">
              {visualUrl && run.visual_render?.status === "READY" ? (
                <>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={visualUrl} alt="Final asset under product dyno review" style={{ width: "100%", display: "block", borderRadius: 8, border: "1px solid var(--border)" }} />
                  <p style={{ margin: "9px 0 0", color: "var(--text-3)", fontSize: 11, fontFamily: "monospace" }}>visual · {shortDigest(report.visual_asset_sha256)}</p>
                </>
              ) : <p style={{ margin: 0, color: "#ffcf86" }}>No READY final visual. Product dyno review is disabled until the full asset exists.</p>}
            </div>
          </article>
        </section>

        <section className="premium-panel" style={{ marginBottom: 18 }}>
          <header className="premium-panel__header">
            <div><div className="premium-kicker">Human authority</div><h2>Editorial judgement</h2><p>Score what you actually see. The browser cannot submit run/content/visual identity; the backend binds those fields after you submit.</p></div>
          </header>
          <div className="premium-panel__body" style={{ display: "grid", gap: 18 }}>
            {SCORE_FIELDS.map(({ key, label, hint }) => (
              <label key={key} style={{ display: "grid", gridTemplateColumns: "minmax(180px, .55fr) minmax(220px, 1fr) 54px", alignItems: "center", gap: 14 }}>
                <span><strong style={{ display: "block", fontSize: 13 }}>{label}</strong><span style={{ color: "var(--text-3)", fontSize: 11 }}>{hint}</span></span>
                <input
                  aria-label={label}
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={scores[key]}
                  disabled={!canReview || saving}
                  onChange={(event) => setScores((current) => ({ ...current, [key]: Number(event.target.value) }))}
                />
                <strong style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{scores[key]}%</strong>
              </label>
            ))}

            <div style={{ display: "grid", gridTemplateColumns: "minmax(180px, .55fr) minmax(220px, 1fr) 54px", gap: 14, alignItems: "center" }}>
              <div><strong style={{ display: "block", fontSize: 13 }}>Final verdict</strong><span style={{ color: "var(--text-3)", fontSize: 11 }}>SIGNED_PASS requires the explicit highest bar plus every independent minimum.</span></div>
              <select value={verdict} disabled={!canReview || saving} onChange={(event) => setVerdict(event.target.value as EditorialVerdict)} style={{ width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-active)", color: "var(--text-1)" }}>
                {VERDICTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
              <span />
            </div>

            <label style={{ display: "grid", gap: 7 }}>
              <strong style={{ fontSize: 13 }}>Review notes</strong>
              <textarea value={notes} disabled={!canReview || saving} onChange={(event) => setNotes(event.target.value)} rows={4} placeholder="One observation per line. What makes this publishable or what still leaks power?" style={{ width: "100%", resize: "vertical", padding: 12, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-active)", color: "var(--text-1)" }} />
            </label>

            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <button className="premium-button" disabled={!canReview || saving} onClick={saveReview}>{saving ? "Binding review…" : report.human_review ? "Re-measure exact asset" : "Save exact-asset review"}</button>
              {!canReview && <span style={{ color: "#ffcf86", fontSize: 12 }}>Requires READY_FOR_REVIEW text and a READY visual asset.</span>}
              {report.human_review && <span className={`premium-status premium-status--${tone(report.human_review.verdict)}`}>{report.human_review.verdict.replaceAll("_", " ")}</span>}
            </div>
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 18 }}>
          <article className="premium-panel">
            <header className="premium-panel__header"><div><h2>Drivetrain losses</h2><p>Where agent/model capability fails to reach the final publishable asset.</p></div></header>
            <div className="premium-panel__body">
              {report.drivetrain_losses.length === 0 ? <p style={{ margin: 0, color: "#a9e7c2" }}>No drivetrain losses detected.</p> : (
                <div style={{ display: "grid", gap: 10 }}>
                  {report.drivetrain_losses.map((loss, index) => (
                    <div key={`${loss.code}-${index}`} style={{ border: "1px solid var(--border)", borderRadius: 9, padding: 11, background: "var(--surface-active)" }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}><span className={`premium-status premium-status--${loss.severity === "HIGH" ? "red" : loss.severity === "MEDIUM" ? "amber" : "blue"}`}>{loss.severity}</span><code style={{ fontSize: 11 }}>{loss.code}</code><span style={{ color: "var(--text-3)", fontSize: 11 }}>{loss.layer}</span></div>
                      <p style={{ margin: 0, color: "var(--text-2)", fontSize: 12, lineHeight: 1.45 }}>{loss.detail}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </article>

          <article className="premium-panel">
            <header className="premium-panel__header"><div><h2>Independent sensors</h2><p>Useful telemetry, never authority and never a substitute for Trust.</p></div></header>
            <div className="premium-panel__body" style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}><span style={{ color: "var(--text-2)" }}>Attention Critic</span><strong>{report.editorial_sensors.editorial_score == null ? "—" : `${Math.round(report.editorial_sensors.editorial_score * 100)}%`}</strong></div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}><span style={{ color: "var(--text-2)" }}>Trust @ Wheels</span><strong>{report.trust_at_wheels.status}</strong></div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}><span style={{ color: "var(--text-2)" }}>Human verdict</span><strong>{report.human_review?.verdict ?? "NOT MEASURED"}</strong></div>
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}><strong style={{ display: "block", marginBottom: 5 }}>Why there is no Wheel HP number</strong><p style={{ margin: 0, color: "var(--text-2)", fontSize: 12, lineHeight: 1.5 }}>A single number would let editorial strength mathematically hide factual failure, or let Trust hide a piece nobody wants to publish. prodAgentic keeps the gauges independent and signs only when all required gates are true.</p></div>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
