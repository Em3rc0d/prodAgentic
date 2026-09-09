"use client";

import { useEffect, useState } from "react";
import {
  fetchRenderPreview,
  fetchRevisionQAEvidence,
  type RenderPreviewV1,
  type RevisionQAEvidenceV1,
} from "../../../lib/rendering";
import styles from "./review.module.css";

export default function RenderPreview({ revisionId }: { revisionId: string }) {
  const [preview, setPreview] = useState<RenderPreviewV1 | null>(null);
  const [qa, setQa] = useState<RevisionQAEvidenceV1 | null>(null);
  const [activePage, setActivePage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [qaError, setQaError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchRenderPreview(revisionId)
      .then((value) => {
        if (!cancelled) {
          setPreview(value);
          setActivePage(0);
        }
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Preview unavailable");
      });
    fetchRevisionQAEvidence(revisionId)
      .then((value) => { if (!cancelled) setQa(value); })
      .catch(() => { if (!cancelled) setQaError(true); });
    return () => { cancelled = true; };
  }, [revisionId]);

  if (error) {
    return <main className={styles.shell}><section className={styles.stateCard}><p className={styles.eyebrow}>Review</p><h1>Preview unavailable</h1><p>{error}</p></section></main>;
  }
  if (!preview) {
    return <main className={styles.shell}><section className={styles.stateCard}><p className={styles.eyebrow}>Review</p><h1>Loading rendered preview…</h1></section></main>;
  }

  const asset = preview.assets[activePage];
  const ready = qa?.readiness === "READY_FOR_REVIEW" || preview.status === "REVIEWABLE";
  const needsAttention = qa?.readiness === "NEEDS_ATTENTION";
  const statusLabel = ready ? "Ready for review" : needsAttention ? "QA · needs attention" : "Rendered · QA pending";

  return (
    <main className={styles.shell} data-testid="s5-review-preview" data-qa-readiness={qa?.readiness || "QA_PENDING"}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Review · QA evidence</p>
          <h1>Rendered visual</h1>
          <p className={styles.subtle}>
            {ready
              ? "QA evidence is complete and this revision is ready for human review. Approval remains a separate downstream authority."
              : needsAttention
                ? "QA found a blocking issue. Valid upstream work is preserved while recovery or user attention resolves the broken layer."
                : "The owned render bytes are awaiting QA. Approval is intentionally unavailable at this stage."}
          </p>
        </div>
        <div className={styles.status} aria-label={statusLabel}>
          <span className={styles.dot} aria-hidden="true" />
          {statusLabel}
        </div>
      </header>

      <section className={styles.workspace}>
        <aside className={styles.rail} aria-label="Rendered pages">
          {preview.assets.map((item, index) => (
            <button
              key={item.asset_id}
              type="button"
              className={`${styles.thumbButton} ${index === activePage ? styles.active : ""}`}
              onClick={() => setActivePage(index)}
              aria-current={index === activePage ? "page" : undefined}
              aria-label={`Show rendered page ${index + 1} of ${preview.assets.length}`}
            >
              <img src={item.url} alt="" className={styles.thumb} />
              <span>{index + 1}</span>
            </button>
          ))}
        </aside>

        <div className={styles.previewStage}>
          {asset ? (
            <figure className={styles.figure}>
              <img
                src={asset.url}
                alt={preview.alt_text || `Rendered ${preview.format} page ${activePage + 1}`}
                className={styles.heroImage}
                width={asset.width}
                height={asset.height}
              />
              <figcaption>
                Page {activePage + 1} of {preview.assets.length} · {asset.width}×{asset.height}
              </figcaption>
            </figure>
          ) : <p>No rendered pages found.</p>}
        </div>

        <aside className={styles.details}>
          <p className={styles.eyebrow}>Evidence</p>
          <dl>
            <div><dt>Revision</dt><dd>{preview.revision_id}</dd></div>
            <div><dt>Format</dt><dd>{preview.format.replaceAll("_", " ")}</dd></div>
            <div><dt>State</dt><dd>{qa?.readiness || preview.qa_state}</dd></div>
            {qa?.qa_report && <div><dt>QA verdict</dt><dd>{qa.qa_report.verdict.replaceAll("_", " ")}</dd></div>}
            {asset && <div><dt>SHA-256</dt><dd className={styles.digest}>{asset.sha256}</dd></div>}
          </dl>

          {qa?.qa_report && (
            <details className={styles.qaEvidence}>
              <summary>QA evidence</summary>
              <div><strong>Report</strong><span>{qa.qa_report.qa_report_id}</span></div>
              <div><strong>Recovery attempt</strong><span>{qa.qa_report.recovery_attempt}</span></div>
              <div><strong>Warnings</strong><span>{qa.qa_report.warnings.length}</span></div>
              <div><strong>Blocking failures</strong><span>{qa.qa_report.failures.length}</span></div>
              <div><strong>Digest</strong><span className={styles.digest}>{qa.qa_report.digest}</span></div>
            </details>
          )}

          <div className={styles.notice}>
            {qaError
              ? "QA evidence is temporarily unavailable; Review does not infer readiness from the preview alone."
              : ready
                ? "S6 has made this revision reviewable. No approval action is exposed here."
                : "S6 must complete QA before this revision can become reviewable. No approval action is exposed here."}
          </div>
        </aside>
      </section>
    </main>
  );
}
