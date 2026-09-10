"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchProfilesV2 } from "@/lib/api";
import { fetchReviewQueue, fetchRuntimeReadiness, type RuntimeReadiness } from "@/lib/r2";
import styles from "./home.module.css";

type Snapshot = {
  profiles: number;
  reviewable: number;
  runtime: RuntimeReadiness;
};

const initial: Snapshot = {
  profiles: 0,
  reviewable: 0,
  runtime: { state: "UNREACHABLE", label: "Checking runtime", detail: "Waiting for an observed readiness result." },
};

export default function HomePage() {
  const [snapshot, setSnapshot] = useState<Snapshot>(initial);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([fetchProfilesV2(), fetchReviewQueue(), fetchRuntimeReadiness()]).then(([profiles, review, runtime]) => {
      if (cancelled) return;
      setSnapshot({
        profiles: profiles.status === "fulfilled" ? profiles.value.count : 0,
        reviewable: review.status === "fulfilled" ? review.value.count : 0,
        runtime: runtime.status === "fulfilled" ? runtime.value : initial.runtime,
      });
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  const nextHref = snapshot.profiles === 0 ? "/profiles" : snapshot.reviewable > 0 ? "/review" : "/create";
  const nextLabel = snapshot.profiles === 0 ? "Create first Profile" : snapshot.reviewable > 0 ? `Review ${snapshot.reviewable} ready` : "Generate next batch";

  return (
    <main className={styles.page} data-testid="r2-home">
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>Control surface</span>
          <h1>What needs attention</h1>
          <p>One product journey. Current authority, review work and runtime uncertainty stay visible without exposing agent plumbing.</p>
        </div>
        <Link href={nextHref} className={styles.primary}>{nextLabel}</Link>
      </header>

      <section className={styles.metrics} aria-label="Current product state">
        <article><small>Profiles</small><strong>{loading ? "—" : snapshot.profiles}</strong><span>{snapshot.profiles ? "Identity authority available" : "Setup required"}</span></article>
        <article><small>Ready for review</small><strong>{loading ? "—" : snapshot.reviewable}</strong><span>{snapshot.reviewable ? "Decision required" : "No review debt"}</span></article>
        <article data-runtime={snapshot.runtime.state}><small>Runtime</small><strong>{loading ? "Checking" : snapshot.runtime.state}</strong><span>{snapshot.runtime.detail}</span></article>
      </section>

      <section className={styles.flow} aria-labelledby="flow-title">
        <div className={styles.sectionHeader}>
          <div><span className={styles.kicker}>Canonical journey</span><h2 id="flow-title">From identity to evidence</h2></div>
          <span className={styles.truth}>Signal ≠ success</span>
        </div>
        <ol>
          <li><span>01</span><div><strong>Profile</strong><small>Freeze identity and version.</small></div></li>
          <li><span>02</span><div><strong>Create</strong><small>Plan fresh work and formats.</small></div></li>
          <li><span>03</span><div><strong>Review</strong><small>Inspect exact owned output.</small></div></li>
          <li><span>04</span><div><strong>Calendar</strong><small>Distribute only approved authority.</small></div></li>
          <li><span>05</span><div><strong>Analytics</strong><small>Learn only from observed evidence.</small></div></li>
        </ol>
      </section>

      {snapshot.runtime.state !== "READY" && !loading && (
        <aside className={styles.warning} role="status"><strong>{snapshot.runtime.label}</strong><span>{snapshot.runtime.detail}</span></aside>
      )}
    </main>
  );
}
