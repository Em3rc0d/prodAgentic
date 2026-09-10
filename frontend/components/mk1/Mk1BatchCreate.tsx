"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { fetchProfilesV2 } from "@/lib/api";
import type { ProfileV2 } from "@/lib/api";
import { createBatchV1 } from "@/lib/mk1-batches";
import type { BatchPlanningResponseV1, PlannedFormat, TargetWindowV1 } from "@/lib/mk1-batches";
import { fetchRuntimeReadiness } from "@/lib/r2";
import { produceContentToReview, type ProductionStage } from "@/lib/r2-production";
import styles from "./mk1-batch-create.module.css";

type WindowPreset = "tomorrow" | "week";
type PieceProgress = { stage: ProductionStage | "WAITING" | "FAILED"; revisionId?: string; error?: string };

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

function stageLabel(stage: PieceProgress["stage"]) {
  return ({ WAITING: "Queued", AGENTS: "Research · write · edit", VISUAL_SPEC: "VisualSpec", RENDER: "Rendering", QA: "QA", REVIEWABLE: "Ready for review", FAILED: "Needs attention" } as const)[stage];
}

const FORMATS: Array<["auto" | PlannedFormat, string]> = [
  ["auto", "Auto"], ["text", "Text"], ["single_image", "Single image"], ["carousel", "Carousel"], ["infographic", "Infographic"],
];

export function Mk1BatchCreate() {
  const router = useRouter();
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
  const [producing, setProducing] = useState(false);
  const [result, setResult] = useState<BatchPlanningResponseV1 | null>(null);
  const [progress, setProgress] = useState<Record<string, PieceProgress>>({});
  const [productionGate, setProductionGate] = useState<string | null>(null);
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
  const selectedEvaluations = useMemo(() => result?.planning_trace.evaluations.filter((evaluation) => evaluation.selected) ?? [], [result]);
  const reviewableCount = useMemo(() => Object.values(progress).filter((item) => item.stage === "REVIEWABLE").length, [progress]);
  const failedCount = useMemo(() => Object.values(progress).filter((item) => item.stage === "FAILED").length, [progress]);

  function updateProgress(contentId: string, value: PieceProgress) {
    setProgress((current) => ({ ...current, [contentId]: { ...current[contentId], ...value } }));
  }

  async function produceBatch(planned: BatchPlanningResponseV1) {
    const runtime = await fetchRuntimeReadiness();
    if (runtime.state !== "READY") {
      setProductionGate(`${runtime.label}: ${runtime.detail}`);
      return;
    }

    setProductionGate(null);
    setProducing(true);
    const initial = Object.fromEntries(planned.content_items.map((item) => [item.content_id, { stage: "WAITING" as const }]));
    setProgress(initial);
    let completed = 0;

    for (const item of planned.content_items) {
      try {
        const outcome = await produceContentToReview(item.content_id, (stage) => updateProgress(item.content_id, { stage }));
        updateProgress(item.content_id, { stage: "REVIEWABLE", revisionId: outcome.revision_id });
        completed += 1;
      } catch (reason) {
        updateProgress(item.content_id, { stage: "FAILED", error: reason instanceof Error ? reason.message : "Production failed" });
      }
    }
    setProducing(false);
    if (completed === planned.content_items.length && completed > 0) router.push("/review");
  }

  async function generate() {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setProgress({});
    setProductionGate(null);
    try {
      const planned = await createBatchV1(profileId, {
        target_window: targetWindow(preset),
        requested_size: size,
        constraints: {
          campaign_goal: goal.trim() || null,
          include_topics: list(includeTopic),
          avoid_topics: list(avoidTopic),
          desired_format: format === "auto" ? null : format,
        },
      });
      setResult(planned);
      await produceBatch(planned);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create this Batch");
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
          <p>Ask for the outcome. prodAgentic checks recent memory, finds fresh angles, freezes the exact Profile version and carries valid work through production to Review.</p>
        </div>
        <div className={styles.signal}><span aria-hidden="true" />Memory-aware</div>
      </header>

      <section className={styles.request} aria-label="Batch request">
        <div className={styles.profileLine}>
          <label>Profile<select value={profileId} onChange={(event) => setProfileId(event.target.value)}>{profiles.length === 0 && <option value="">No Profile available</option>}{profiles.map((item) => <option key={item.profile_id} value={item.profile_id}>{item.name} · v{item.current_version}</option>)}</select></label>
          <div><small>Exact identity</small><strong>{profile ? `Profile v${profile.current_version}` : "Create a Profile first"}</strong></div>
        </div>

        <div className={styles.controls}>
          <div><span className={styles.label}>When</span><div className={styles.segmented}><button aria-pressed={preset === "tomorrow"} onClick={() => setPreset("tomorrow")}>Tomorrow</button><button aria-pressed={preset === "week"} onClick={() => setPreset("week")}>This week</button></div></div>
          <div><span className={styles.label}>Pieces</span><div className={styles.segmented}>{[1, 4, 7].map((value) => <button key={value} aria-pressed={size === value} onClick={() => setSize(value)}>{value}</button>)}</div></div>
        </div>

        <button className={styles.advancedToggle} aria-expanded={advanced} onClick={() => setAdvanced((value) => !value)}>{advanced ? "Hide constraints" : "Add optional constraints"}<span aria-hidden="true">{advanced ? "−" : "+"}</span></button>
        {advanced && <div className={styles.advanced}>
          <label>Goal<input value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="e.g. teach one useful concept" /></label>
          <label>Include topic<input value={includeTopic} onChange={(event) => setIncludeTopic(event.target.value)} placeholder="topic, optional" /></label>
          <label>Avoid for this batch<input value={avoidTopic} onChange={(event) => setAvoidTopic(event.target.value)} placeholder="topic, optional" /></label>
          <label>Format<select value={format} onChange={(event) => setFormat(event.target.value as "auto" | PlannedFormat)}>{FORMATS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>}

        <button className={styles.primary} disabled={busy || producing || !profileId} onClick={generate}>{producing ? "Producing reviewable work…" : busy ? "Finding fresh angles…" : "Generate next batch"}</button>
        {error && <p role="alert" className={styles.error}>{error}</p>}
      </section>

      {result && <section className={styles.result} aria-live="polite">
        <div className={styles.resultHeader}>
          <div><span className={styles.kicker}>Batch planned</span><h2>{result.batch.selected_size} of {result.batch.requested_size} ideas committed</h2><p>{result.batch.selected_size < result.batch.requested_size ? "We returned fewer ideas instead of repeating recent content." : "Freshness and current-batch diversity gates passed."}</p></div>
          <div className={styles.metrics}><div><small>Memory</small><strong>{result.memory_count}</strong></div><div><small>Pool</small><strong>{result.batch.summary_counts.candidates_generated}</strong></div><div><small>Blocked</small><strong>{result.batch.summary_counts.candidates_blocked + result.batch.summary_counts.candidates_rewrite}</strong></div></div>
        </div>
        {result.batch.shortfall_reason && <div className={styles.shortfall}>{result.batch.shortfall_reason}</div>}
        {productionGate && <div className={styles.productionGate}><div><strong>Production is paused truthfully.</strong><span>{productionGate}</span></div><button onClick={() => void produceBatch(result)} disabled={producing}>Retry production</button></div>}

        <div className={styles.cards}>
          {result.content_items.map((item) => {
            const plan = result.plans.find((entry) => entry.content_id === item.content_id);
            const evaluation = selectedEvaluations.find((entry) => entry.candidate.candidate_id === plan?.plan.candidate_id);
            const state = progress[item.content_id];
            return <article key={item.content_id} className={styles.card} data-production-state={state?.stage || "PLANNED"}>
              <div className={styles.cardMeta}><span>{item.role}</span><span>{item.format.replace("_", " ")}</span></div>
              <h3>{item.canonical_topic.replaceAll(".", " ")}</h3><p>{item.angle}</p>
              {state && <div className={styles.progressRow}><span className={styles.progressDot} aria-hidden="true" /><strong>{stageLabel(state.stage)}</strong>{state.error && <small>{state.error}</small>}</div>}
              <footer><span>{item.hook_pattern}</span><span>{evaluation?.novelty.verdict === "PASS_WITH_WARNING" ? "Fresh · review note" : "Fresh"}</span></footer>
            </article>;
          })}
        </div>

        {(reviewableCount > 0 || failedCount > 0) && <div className={styles.productionSummary}><span>{reviewableCount} reviewable · {failedCount} need attention</span>{reviewableCount > 0 && <Link href="/review">Open Review →</Link>}</div>}
        <details className={styles.evidence}><summary>Planning evidence</summary><div><span>trace {result.planning_trace.trace_id}</span><span>{result.planning_trace.evaluations.length} candidates evaluated</span><span>{result.planning_trace.evaluations.filter((item) => item.novelty.verdict === "BLOCKED").length} hard collisions</span></div></details>
      </section>}
    </main>
  );
}
