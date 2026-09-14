"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { resolveBackendAssetUrl } from "@/lib/api";
import { fetchReviewQueue, type ReviewQueueItem } from "@/lib/r2";
import styles from "./review-queue.module.css";

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReviewQueue()
      .then((payload) => { if (!cancelled) setItems(payload.revisions); })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Review queue unavailable"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <main className={styles.page} data-testid="r2-review-queue">
      <header className={styles.header}>
        <div><span className={styles.kicker}>Human authority</span><h1>Review</h1><p>Review the actual creative before approval. Visual bytes, copy, QA evidence and lineage remain bound to the exact revision.</p></div>
        <Link href="/create" className={styles.secondary}>Create next batch</Link>
      </header>

      {error && <div className={styles.error} role="alert"><strong>Review queue unavailable</strong><span>{error}</span></div>}

      <section className={styles.queue} aria-live="polite">
        {loading ? (
          <div className={styles.empty}>Loading review authority…</div>
        ) : items.length === 0 ? (
          <div className={styles.empty}><h2>Nothing is waiting for review.</h2><p>When QA makes a revision REVIEWABLE, the finished creative appears here. Failed or QA-pending work is intentionally excluded.</p><Link href="/create">Generate work</Link></div>
        ) : items.map((item) => {
          const previewUrl = item.preview_asset_id ? resolveBackendAssetUrl(`/api/render-assets/${encodeURIComponent(item.preview_asset_id)}/content`) : null;
          return <article key={item.revision_id} className={styles.item} data-testid="r4-review-card">
            <div className={styles.itemTop}><span className={styles.status}>REVIEWABLE</span><time dateTime={item.created_at}>{formatTime(item.created_at)}</time></div>
            <div className={styles.contentGrid}>
              {previewUrl ? <Link className={styles.previewLink} href={`/review/${encodeURIComponent(item.revision_id)}`} aria-label={`Open visual revision ${item.revision_id}`}><img className={styles.preview} src={previewUrl} alt="" loading="lazy" /></Link> : <div className={styles.textOnlyPreview}><span>TEXT</span><strong>{item.hook || item.title || "Text post"}</strong></div>}
              <div className={styles.copy}><span className={styles.format}>{(item.format || "content").replaceAll("_", " ")}</span><h2>{item.title || item.hook || item.content_id}</h2>{item.title && item.hook && <p>{item.hook}</p>}</div>
            </div>
            <footer><span>revision {item.revision_id.slice(0, 12)}</span><Link href={`/review/${encodeURIComponent(item.revision_id)}`}>Review exact creative →</Link></footer>
          </article>;
        })}
      </section>
    </main>
  );
}
