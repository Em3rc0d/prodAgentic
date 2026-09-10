"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  AnalyticsOverview,
  MetricSnapshot,
  collectPublicationAnalytics,
  enableLinkedInAnalytics,
  fetchAnalyticsOverview,
} from "@/lib/analytics";
import { mk1AnalyticsEnabled } from "@/lib/mk1-feature-flags";
import styles from "./analytics.module.css";

function formatMetric(value: number | null) {
  return value === null ? "Unavailable" : new Intl.NumberFormat().format(value);
}

function formatTime(value?: string | null) {
  if (!value) return "No successful sync yet";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function freshness(value?: string | null, state?: AnalyticsOverview["freshness_state"]) {
  if (!value) return { label: state === "DEGRADED" ? "Provider degraded" : "No evidence yet", stale: true };
  const ageMs = Date.now() - new Date(value).getTime();
  const hours = Math.max(0, Math.round(ageMs / 3_600_000));
  if (state === "DEGRADED") return { label: "Provider degraded", stale: true };
  if (state === "STALE") return { label: `Stale · ${hours}h old`, stale: true };
  if (state === "COMPLETE_V1") return { label: "Lifecycle complete · latest evidence retained", stale: false };
  if (hours < 1) return { label: "Fresh · less than 1h", stale: false };
  return { label: `Fresh · ${hours}h old`, stale: false };
}

function metricLabel(metric: string) {
  return metric.replaceAll("_", " ").replace(/\b\w/g, (value) => value.toUpperCase());
}

function providerEvidence(snapshot: MetricSnapshot) {
  const available = Object.entries(snapshot.raw_available_metrics).map(([name, value]) => ({
    name,
    value,
    available: true as const,
  }));
  const unavailable = snapshot.unavailable_metrics.map((name) => ({
    name,
    value: null,
    available: false as const,
  }));
  return [...available, ...unavailable];
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mk1AnalyticsEnabled) return;
    let cancelled = false;
    fetchAnalyticsOverview()
      .then((payload) => {
        if (cancelled) return;
        setOverview(payload);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Analytics could not be loaded");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const fresh = useMemo(
    () => freshness(overview?.last_success_at, overview?.freshness_state),
    [overview?.last_success_at, overview?.freshness_state],
  );

  const interactionCoverage = useMemo(
    () => Object.values(overview?.interaction_coverage || {}).reduce((sum, value) => sum + value, 0),
    [overview?.interaction_coverage],
  );

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setOverview(await fetchAnalyticsOverview());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analytics could not be loaded");
    } finally {
      setLoading(false);
    }
  }

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analytics action failed");
    } finally {
      setBusy(null);
    }
  }

  if (!mk1AnalyticsEnabled) {
    return (
      <main className={styles.page} data-testid="s11-analytics">
        <section className={styles.emptyState}>
          <span className={styles.eyebrow}>Evidence</span>
          <h1>Analytics is not enabled for this rollout.</h1>
          <p>Publication evidence remains authoritative. No missing provider metric is treated as zero.</p>
        </section>
      </main>
    );
  }

  const capability = overview?.capability;
  const evidence = overview?.latest_snapshots || [];

  return (
    <main className={styles.page} data-testid="s11-analytics" data-freshness={overview?.freshness_state || "UNKNOWN"}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>Measurement</span>
          <h1>Analytics</h1>
          <p>Evidence for better decisions — not a vanity scoreboard. Coverage and freshness stay visible beside every summary.</p>
        </div>
        <div className={styles.capabilityCard} data-ready={capability?.analytics_available ? "true" : "false"}>
          <div>
            <small>LinkedIn analytics</small>
            <strong>{capability?.analytics_available ? "Ready" : capability?.connected ? "Permission needed" : "Unavailable"}</strong>
            <span>{capability?.reason || `API ${capability?.api_version || "—"}`}</span>
          </div>
          {capability?.connected && !capability.analytics_scope_granted ? (
            <button
              className={styles.primaryButton}
              onClick={() => run("enable", enableLinkedInAnalytics)}
              disabled={busy === "enable"}
            >
              Enable analytics
            </button>
          ) : !capability?.connected ? (
            <Link className={styles.secondaryButton} href="/calendar">Open Calendar</Link>
          ) : null}
        </div>
      </header>

      {error && <div className={styles.error} role="alert">{error}</div>}

      <section className={styles.summaryGrid} aria-label="Analytics overview">
        <article className={styles.metricCard}>
          <span>Published</span>
          <strong>{overview?.published_content_count ?? "—"}</strong>
          <small>Authoritative publications</small>
        </article>
        <article className={styles.metricCard}>
          <span>Measured</span>
          <strong>{overview?.measured_publication_count ?? "—"}</strong>
          <small>Posts with a successful snapshot</small>
        </article>
        <article className={styles.metricCard} data-unavailable={overview?.impressions_or_views === null ? "true" : "false"}>
          <span>Impressions / views</span>
          <strong>{formatMetric(overview?.impressions_or_views ?? null)}</strong>
          <small>{overview?.impressions_coverage_count ?? 0} posts in coverage</small>
        </article>
        <article className={styles.metricCard} data-unavailable={overview?.interactions === null ? "true" : "false"}>
          <span>Interactions</span>
          <strong>{formatMetric(overview?.interactions ?? null)}</strong>
          <small>{interactionCoverage} available metric observations</small>
        </article>
      </section>

      <section className={styles.freshness} data-stale={fresh.stale ? "true" : "false"}>
        <div>
          <span className={styles.freshnessDot} aria-hidden="true" />
          <div>
            <strong>{fresh.label}</strong>
            <small>Last successful provider sync · {formatTime(overview?.last_success_at)}</small>
          </div>
        </div>
        <button className={styles.secondaryButton} onClick={() => void refresh()} disabled={loading}>
          Refresh evidence
        </button>
      </section>

      <section className={styles.evidenceSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.eyebrow}>Latest observations</span>
            <h2>Publication evidence</h2>
          </div>
          <small>{overview?.automatic_collection_enabled ? "Automatic collection enabled" : "Automatic collection disabled"}</small>
        </div>

        {loading ? (
          <div className={styles.emptyState}>Loading analytics evidence…</div>
        ) : evidence.length === 0 ? (
          <div className={styles.emptyState}>
            <h3>No successful metric snapshots yet.</h3>
            <p>Published content remains valid. Analytics will appear when provider permission and a successful collection are available.</p>
          </div>
        ) : (
          <div className={styles.evidenceList}>
            {evidence.map((snapshot: MetricSnapshot) => (
              <article key={snapshot.metric_snapshot_id} className={styles.evidenceCard}>
                <div className={styles.evidenceTop}>
                  <div>
                    <small>Publication</small>
                    <strong>{snapshot.publication_id}</strong>
                  </div>
                  <div className={styles.snapshotMeta}>
                    <span>{snapshot.collection_bucket}</span>
                    <time dateTime={snapshot.captured_at}>{formatTime(snapshot.captured_at)}</time>
                  </div>
                </div>
                <div className={styles.metricRows}>
                  {providerEvidence(snapshot).map((metric) => (
                    <div key={metric.name} className={styles.metricRow} data-available={metric.available ? "true" : "false"}>
                      <span>{metricLabel(metric.name)}</span>
                      <strong>{metric.available ? formatMetric(metric.value) : "Unavailable"}</strong>
                      <small>{metric.available ? "Provider observation" : "Provider did not expose this metric"}</small>
                    </div>
                  ))}
                </div>
                <div className={styles.snapshotMeta}>
                  <span>Source · {snapshot.source_version}</span>
                  <span>Next expected · {formatTime(snapshot.freshness.expected_next_sync_at)}</span>
                </div>
                {overview?.automatic_collection_enabled && capability?.analytics_available && (
                  <button
                    className={styles.secondaryButton}
                    onClick={() => run(`collect-${snapshot.publication_id}`, () => collectPublicationAnalytics(snapshot.publication_id))}
                    disabled={busy === `collect-${snapshot.publication_id}`}
                  >
                    Collect fresh snapshot
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
