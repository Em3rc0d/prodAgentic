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
import styles from "./publishing.module.css";

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
  const readyCount = useMemo(() => queue.filter((run) => run.status === "APPROVED").length, [queue]);
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

  const statusText = connected
    ? "Connected"
    : publisher?.status === "RECONNECT_REQUIRED"
      ? "Reconnect required"
      : "Not connected";

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <div className={styles.eyebrow}>Distribution control</div>

        <header className={styles.hero}>
          <div>
            <h1 className={styles.title}>LinkedIn publishing</h1>
            <p className={styles.subtitle}>
              Connect once. Approve deliberately. Publish exactly what was reviewed—never a mutable draft.
            </p>
          </div>
          <div className={styles.heroMetric} aria-label={`${readyCount} posts ready to publish`}>
            <div className={styles.heroMetricValue}>{readyCount}</div>
            <div className={styles.heroMetricLabel}>Ready to publish</div>
          </div>
        </header>

        <section className={styles.grid}>
          <article className={`${styles.panel} ${styles.accountCard}`}>
            <div className={styles.accountTop}>
              <div className={styles.accountIdentity}>
                <div className={styles.avatar}>{initials(publisher?.display_name)}</div>
                <div style={{ minWidth: 0 }}>
                  <div className={styles.accountLabel}>Connected identity</div>
                  <div className={styles.accountName}>
                    {connected ? publisher?.display_name || "LinkedIn member" : "LinkedIn member account"}
                  </div>
                  <div className={styles.accountMeta}>
                    {connected
                      ? "Personal publishing authority is active"
                      : publisher?.reason || "Connect a member account before publishing"}
                  </div>
                </div>
              </div>
              <span className={`${styles.status} ${connected ? styles.statusConnected : styles.statusWarning}`}>
                {statusText}
              </span>
            </div>

            <div className={styles.accountBottom}>
              <div>
                <div className={styles.detailLabel}>Token validity</div>
                <div className={styles.detailValue}>
                  {connected && publisher?.expires_at ? `Until ${formatDate(publisher.expires_at)}` : "No active token"}
                </div>
              </div>
              <div>
                <div className={styles.detailLabel}>Provider contract</div>
                <div className={styles.detailValue}>LinkedIn API {publisher?.api_version || "—"}</div>
              </div>
              {connected ? (
                <button className={styles.buttonGhost} onClick={disconnect} disabled={connectionBusy}>
                  {connectionBusy ? "Disconnecting…" : "Disconnect"}
                </button>
              ) : (
                <button
                  className={styles.button}
                  onClick={startLinkedInConnection}
                  disabled={connectionBusy || publisher?.configured === false}
                >
                  {connectionBusy ? "Connecting…" : publisher?.status === "RECONNECT_REQUIRED" ? "Reconnect LinkedIn" : "Connect LinkedIn"}
                </button>
              )}
            </div>
          </article>

          <aside className={`${styles.panel} ${styles.controlCard}`}>
            <div className={styles.controlTitle}>Publishing guardrail</div>
            <p className={styles.controlCopy}>
              Distribution is intentionally downstream of approval. Connection alone never authorizes a post.
            </p>
            <div className={styles.steps}>
              <div className={`${styles.step} ${connected ? styles.stepDone : ""}`}>
                <div className={styles.stepIndex}>{connected ? "✓" : "01"}</div>
                <div>
                  <div className={styles.stepTitle}>Connect identity</div>
                  <div className={styles.stepSub}>{connected ? "Member authority verified" : "OAuth connection required"}</div>
                </div>
              </div>
              <div className={`${styles.step} ${readyCount > 0 ? styles.stepDone : ""}`}>
                <div className={styles.stepIndex}>{readyCount > 0 ? "✓" : "02"}</div>
                <div>
                  <div className={styles.stepTitle}>Approve content</div>
                  <div className={styles.stepSub}>{readyCount > 0 ? `${readyCount} approved bundle${readyCount === 1 ? "" : "s"}` : "Human approval is required"}</div>
                </div>
              </div>
              <div className={styles.step}>
                <div className={styles.stepIndex}>03</div>
                <div>
                  <div className={styles.stepTitle}>Publish exact bundle</div>
                  <div className={styles.stepSub}>External receipt is persisted after success</div>
                </div>
              </div>
            </div>
          </aside>
        </section>

        {error && <div className={styles.error}>{error}</div>}

        <section>
          <div className={styles.sectionHeader}>
            <div>
              <div className={styles.sectionLabel}>Publication queue</div>
              <div className={styles.sectionMeta}>Approved, in-flight, and published ContentRuns appear here.</div>
            </div>
          </div>

          {loading && <div className={`${styles.panel} ${styles.loading}`}>Loading publication queue…</div>}

          {!loading && queue.length === 0 && (
            <div className={styles.empty}>
              <div className={styles.emptyIcon} aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M4 12.5 20 5l-6.5 14-2.7-5.8L4 12.5Z" /><path d="m10.8 13.2 3.7-3.6" /></svg>
              </div>
              <div>
                <div className={styles.emptyTitle}>Your connection is ready. The queue is intentionally empty.</div>
                <p className={styles.emptyCopy}>
                  Create a ContentRun, review the final text and visual, then approve it. Only that immutable approval bundle becomes publishable.
                </p>
              </div>
              <div className={styles.emptyActions}>
                <Link href="/" className={styles.primaryLink}>Create content</Link>
                <Link href="/library" className={styles.secondaryLink}>Open library</Link>
              </div>
            </div>
          )}

          {!loading && queue.length > 0 && (
            <div className={styles.queue}>
              {queue.map((run) => {
                const publication = (run.publication ?? null) as PublicationSnapshot | null;
                const canPublish = run.status === "APPROVED" && connected && activeId !== run.run_id;
                return (
                  <article key={run.run_id} className={styles.runCard}>
                    <div style={{ minWidth: 0 }}>
                      <div className={styles.runTopline}>
                        <span className={styles.runStatus}>{run.status}</span>
                        <span className={styles.runId}>RUN {run.run_id.slice(0, 8)}</span>
                      </div>
                      <h2 className={styles.runTitle}>{run.idea}</h2>
                      <p className={styles.runTopic}>{run.topic}</p>
                      {run.approval && (
                        <div className={styles.runEvidence}>
                          Approved {formatDate(run.approval.approved_at)} · bundle {run.approval.bundle_sha256.slice(0, 14)}… · {run.approval.include_visual ? "text + visual" : "text only"}
                        </div>
                      )}
                      {publication && (
                        <div className={styles.runEvidence}>
                          Publication {publication.status} · started {formatDate(publication.started_at)}
                          {publication.external_post_urn ? ` · ${publication.external_post_urn}` : ""}
                          {publication.error_message ? ` · ${publication.error_message}` : ""}
                        </div>
                      )}
                    </div>
                    <div className={styles.runActions}>
                      <Link href={`/library/${encodeURIComponent(run.run_id)}`} className={styles.secondaryLink}>Review evidence</Link>
                      {run.status === "APPROVED" && (
                        <button className={styles.button} onClick={() => publish(run)} disabled={!canPublish}>
                          {activeId === run.run_id ? "Publishing…" : connected ? "Publish to LinkedIn" : "Connect LinkedIn first"}
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
