"use client";

import { useEffect, useState } from "react";
import { fetchRenderPreview, type RenderPreviewV1 } from "../../../lib/rendering";
import styles from "./review.module.css";

export default function RenderPreview({ revisionId }: { revisionId: string }) {
  const [preview, setPreview] = useState<RenderPreviewV1 | null>(null);
  const [activePage, setActivePage] = useState(0);
  const [error, setError] = useState<string | null>(null);

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
    return () => { cancelled = true; };
  }, [revisionId]);

  if (error) {
    return <main className={styles.shell}><section className={styles.stateCard}><p className={styles.eyebrow}>Review</p><h1>Preview unavailable</h1><p>{error}</p></section></main>;
  }
  if (!preview) {
    return <main className={styles.shell}><section className={styles.stateCard}><p className={styles.eyebrow}>Review</p><h1>Loading rendered preview…</h1></section></main>;
  }

  const asset = preview.assets[activePage];
  return (
    <main className={styles.shell} data-testid="s5-review-preview">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Review · S5 render preview</p>
          <h1>Rendered visual</h1>
          <p className={styles.subtle}>The owned render bytes are ready for QA. Approval is intentionally unavailable at this stage.</p>
        </div>
        <div className={styles.status} aria-label="Rendered, QA pending">
          <span className={styles.dot} aria-hidden="true" />
          Rendered · QA pending
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
            <div><dt>State</dt><dd>{preview.qa_state}</dd></div>
            {asset && <div><dt>SHA-256</dt><dd className={styles.digest}>{asset.sha256}</dd></div>}
          </dl>
          <div className={styles.notice}>
            S6 must complete QA before this revision can become reviewable. No approval action is exposed here.
          </div>
        </aside>
      </section>
    </main>
  );
}
