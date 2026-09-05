"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchProfilesV2 } from "@/lib/api";
import type { ProfileV2 } from "@/lib/api";
import { createBatchV1 } from "@/lib/mk1-batches";
import type { BatchPlanningResponseV1, PlannedFormat, TargetWindowV1 } from "@/lib/mk1-batches";
import styles from "./mk1-batch-create.module.css";


type WindowPreset = "tomorrow" | "week";

function localMidnight(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function targetWindow(preset: WindowPreset): TargetWindowV1 {
  const now = new Date();
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  if (preset === "tomorrow") {
    const start = localMidnight(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
    const end = localMidnight(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 2));
    return { start_at: start.toISOString(), end_at: end.toISOString(), timezone };
  }
  const start = new Date(now);
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 7, 23, 59, 59, 999);
  return { start_at: start.toISOString(), end_at: end.toISOString(), timezone };
}

function list(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 12);
}

const FORMATS: Array<["auto" | PlannedFormat, string]> = [
  ["auto", "Auto"],
  ["text", "Text"],
  ["single_image", "Single image"],
  ["carousel", "Carousel"],
  ["infographic", "Infographic"],
];

export function Mk1BatchCreate() {
  const [profiles, setProfiles] = useState<ProfileV2[]>([]);
  const [profileId, setProfileId] = useState("");
  const [preset, setPreset] = useState<WindowPreset>("tomorrow");
  const [size, setSize] = useState(4);
  const [advanced, setAdvanced] = useState(false);
  const [includeTopic, setIncludeTopic] = useState("");
  const [avoidTopic, setAvoidTopic] = useState("");
  const [goal, setGoal] = useState("");
  const [format, setFormat] = useState<"auto" | PlannedFormat>("auto");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BatchPlanningResponseV1 | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProfilesV2()
      .then((data) => {
        setProfiles(data.profiles);
        setProfileId((current) => current || data.profiles[0]?.profile_id || "");
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Profiles are temporarily unavailable"));
  }, []);

  const profile = useMemo(() => profiles.find((item) => item.profile_id === profileId) ?? null, [profiles, profileId]);
  const selectedEvaluations = useMemo(
    () => result?.planning_trace.evaluations.filter((evaluation) => evaluation.selected) ?? [],
    [result],
  );

  async function generate() {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await createBatchV1(profileId, {
        target_window: targetWindow(preset),
        requested_size: size,
        constraints: {
          campaign_goal: goal.trim() || null,
          include_topics: list(includeTopic),
          avoid_topics: list(avoidTopic),
          desired_format: format === "auto" ? null : format,
        },
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not plan this Batch");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>Planning intelligence</span>
          <h1>Create for {profile?.name || "your Profile"}</h1>
          <p>Ask for the outcome. prodAgentic checks recent memory, finds fresh angles and freezes the exact Profile version before production.</p>
        </div>
        <div className={styles.signal}><span aria-hidden="true" />Memory-aware</div>
      </header>

      <section className={styles.request} aria-label="Batch request">
        <div className={styles.profileLine}>
          <label>
            Profile
            <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              {profiles.length === 0 && <option value="">No Profile available</option>}
              {profiles.map((item) => <option key={item.profile_id} value={item.profile_id}>{item.name} · v{item.current_version}</option>)}
            </select>
          </label>
          <div><small>Exact identity</small><strong>{profile ? `Profile v${profile.current_version}` : "Create a Profile first"}</strong></div>
        </div>

        <div className={styles.controls}>
          <div>
            <span className={styles.label}>When</span>
            <div className={styles.segmented}>
              <button aria-pressed={preset === "tomorrow"} onClick={() => setPreset("tomorrow")}>Tomorrow</button>
              <button aria-pressed={preset === "week"} onClick={() => setPreset("week")}>This week</button>
            </div>
          </div>
          <div>
            <span className={styles.label}>Pieces</span>
            <div className={styles.segmented}>
              {[1, 4, 7].map((value) => <button key={value} aria-pressed={size === value} onClick={() => setSize(value)}>{value}</button>)}
            </div>
          </div>
        </div>

        <button className={styles.advancedToggle} aria-expanded={advanced} onClick={() => setAdvanced((value) => !value)}>
          {advanced ? "Hide constraints" : "Add optional constraints"}
          <span aria-hidden="true">{advanced ? "−" : "+"}</span>
        </button>

        {advanced && (
          <div className={styles.advanced}>
            <label>Goal<input value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="e.g. teach one useful concept" /></label>
            <label>Include topic<input value={includeTopic} onChange={(event) => setIncludeTopic(event.target.value)} placeholder="topic, optional" /></label>
            <label>Avoid for this batch<input value={avoidTopic} onChange={(event) => setAvoidTopic(event.target.value)} placeholder="topic, optional" /></label>
            <label>Format<select value={format} onChange={(event) => setFormat(event.target.value as "auto" | PlannedFormat)}>{FORMATS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </div>
        )}

        <button className={styles.primary} disabled={busy || !profileId} onClick={generate}>
          {busy ? "Finding fresh angles…" : "Generate next batch"}
        </button>
        {error && <p role="alert" className={styles.error}>{error}</p>}
      </section>

      {result && (
        <section className={styles.result} aria-live="polite">
          <div className={styles.resultHeader}>
            <div>
              <span className={styles.kicker}>Batch planned</span>
              <h2>{result.batch.selected_size} of {result.batch.requested_size} ideas committed</h2>
              <p>{result.batch.selected_size < result.batch.requested_size
                ? "We returned fewer ideas instead of repeating recent content."
                : "Freshness and current-batch diversity gates passed."}</p>
            </div>
            <div className={styles.metrics}>
              <div><small>Memory</small><strong>{result.memory_count}</strong></div>
              <div><small>Pool</small><strong>{result.batch.summary_counts.candidates_generated}</strong></div>
              <div><small>Blocked</small><strong>{result.batch.summary_counts.candidates_blocked + result.batch.summary_counts.candidates_rewrite}</strong></div>
            </div>
          </div>

          {result.batch.shortfall_reason && <div className={styles.shortfall}>{result.batch.shortfall_reason}</div>}

          <div className={styles.cards}>
            {result.content_items.map((item) => {
              const evaluation = selectedEvaluations.find((entry) => entry.candidate.candidate_id === result.plans.find((plan) => plan.content_id === item.content_id)?.artifact_id);
              return (
                <article key={item.content_id} className={styles.card}>
                  <div className={styles.cardMeta}><span>{item.role}</span><span>{item.format.replace("_", " ")}</span></div>
                  <h3>{item.canonical_topic.replaceAll(".", " ")}</h3>
                  <p>{item.angle}</p>
                  <footer><span>{item.hook_pattern}</span><span>{evaluation?.novelty.verdict === "PASS_WITH_WARNING" ? "Fresh · review note" : "Fresh"}</span></footer>
                </article>
              );
            })}
          </div>

          <details className={styles.evidence}>
            <summary>Planning evidence</summary>
            <div>
              <span>trace {result.planning_trace.trace_id}</span>
              <span>{result.planning_trace.evaluations.length} candidates evaluated</span>
              <span>{result.planning_trace.evaluations.filter((item) => item.novelty.verdict === "BLOCKED").length} hard collisions</span>
            </div>
          </details>
        </section>
      )}
    </main>
  );
}
