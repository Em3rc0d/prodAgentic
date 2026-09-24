"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { fetchProfilesV2 } from "@/lib/api";
import type { ProfileV2 } from "@/lib/api";
import { createBatchV1, fetchBatchV1 } from "@/lib/mk1-batches";
import type { BatchPlanningResponseV1, PlannedFormat, TargetWindowV1 } from "@/lib/mk1-batches";
import { fetchRuntimeReadiness } from "@/lib/r2";
import { produceContentToReview, resumeContentToReview, recoverContent, fetchContentRecovery, type RecoveryDecision, type ProductionStage } from "@/lib/r2-production";
import styles from "./mk1-batch-create.module.css";

type WindowPreset = "tomorrow" | "week";
type PieceProgress = { stage: ProductionStage | "WAITING" | "FAILED"; revisionId?: string; error?: string; recovery?: RecoveryDecision };

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

const MAX_AUTOMATIC_RECOVERY_HOPS = 3;

function canRecoverAutomatically(decision?: RecoveryDecision): boolean {
  if (!decision) return false;
  if (decision.action === "REPLAN_CONTENT") return true;
  return decision.action === "RESUME_PIPELINE" && decision.retryable;
}

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

  useEffect(() => {
    const batchId = new URLSearchParams(window.location.search).get("batch");
    if (!batchId) return;
    let active = true;
    void (async () => {
      try {
        const saved = await fetchBatchV1(batchId);
        const states = await Promise.all(saved.content_items.map(async (item) => {
          const recovery = await fetchContentRecovery(item.content_id);
          return [item.content_id, {
            stage: item.editorial_state === "READY_FOR_REVIEW" || item.editorial_state === "APPROVED" ? "REVIEWABLE" : ["RETRY_PRODUCTION", "REPLAN_CONTENT", "HUMAN_ACTION_REQUIRED"].includes(recovery.action) ? "FAILED" : "WAITING",
            recovery,
            error: recovery.action === "NONE" ? undefined : recovery.safe_message,
          } as PieceProgress] as const;
        }));
        if (active) {
          setResult(saved);
          setProfileId(saved.batch.profile_id);
          setProgress(Object.fromEntries(states));
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Saved batch unavailable");
      }
    })();
    return () => { active = false; };
  }, []);

  const profile = useMemo(() => profiles.find((item) => item.profile_id === profileId) ?? null, [profiles, profileId]);
  const selectedEvaluations = useMemo(() => result?.planning_trace.evaluations.filter((evaluation) => evaluation.selected) ?? [], [result]);
  const reviewableCount = useMemo(() => result?.content_items.filter((item) => progress[item.content_id]?.stage === "REVIEWABLE").length ?? 0, [progress, result]);
  const failedCount = useMemo(() => result?.content_items.filter((item) => progress[item.content_id]?.stage === "FAILED").length ?? 0, [progress, result]);

  function updateProgress(contentId: string, value: PieceProgress) {
    setProgress((current) => ({ ...current, [contentId]: { ...current[contentId], ...value } }));
  }

  async function produceSlot(contentId: string, batchId: string, resume = false): Promise<boolean> {
    let activeId = contentId;
    let firstAttempt = true;
    let pendingDecision: RecoveryDecision | undefined;

    for (let hop = 0; hop <= MAX_AUTOMATIC_RECOVERY_HOPS; hop += 1) {
      try {
        if (pendingDecision) {
          const decision = pendingDecision;
          pendingDecision = undefined;

          const previousId = activeId;
          const outcome = await recoverContent(
            activeId,
            decision,
            (stage) => updateProgress(activeId, { stage, error: undefined, recovery: undefined }),
            async (replacementId) => {
              activeId = replacementId;
              const refreshed = await fetchBatchV1(batchId);
              setResult(refreshed);
              setProgress((current) => {
                const next = { ...current };
                delete next[previousId];
                next[replacementId] = { stage: "WAITING" };
                return next;
              });
            },
          );
          activeId = outcome.content_id;
          updateProgress(activeId, {
            stage: "REVIEWABLE",
            revisionId: outcome.revision_id,
            error: undefined,
            recovery: undefined,
          });
          return true;
        }

        const produce = firstAttempt && resume ? resumeContentToReview : produceContentToReview;
        firstAttempt = false;
        const outcome = await produce(
          activeId,
          (stage) => updateProgress(activeId, { stage, error: undefined, recovery: undefined }),
        );
        updateProgress(outcome.content_id, {
          stage: "REVIEWABLE",
          revisionId: outcome.revision_id,
          error: undefined,
          recovery: undefined,
        });
        return true;
      } catch (reason) {
        firstAttempt = false;
        const recovery = await fetchContentRecovery(activeId).catch(() => undefined);
        updateProgress(activeId, {
          stage: "FAILED",
          error: reason instanceof Error ? reason.message : "Production failed",
          recovery,
        });
        if (hop >= MAX_AUTOMATIC_RECOVERY_HOPS || !canRecoverAutomatically(recovery)) {
          return false;
        }
        pendingDecision = recovery;
      }
    }
    return false;
  }

  async function produceBatch(planned: BatchPlanningResponseV1, resume = false) {
    setProducing(true);
    setError(null);
    try {
      const runtime = await fetchRuntimeReadiness();
      if (runtime.state !== "READY") {
        setProductionGate(`${runtime.label}: ${runtime.detail}`);
        return;
      }
      setProductionGate(null);
      if (!resume) setProgress(Object.fromEntries(planned.content_items.map((item) => [item.content_id, { stage: "WAITING" as const }])));
      let completed = 0;
      for (const item of planned.content_items) {
        if (await produceSlot(item.content_id, planned.batch.batch_id, resume)) {
          completed += 1;
        }
      }
      if (completed === planned.content_items.length && completed > 0) router.push("/review");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Production is unavailable. Retry this batch.");
    } finally {
      setProducing(false);
    }
  }

  async function recoverPiece(contentId: string) {
    if (!result || producing) return;
    setProducing(true);
    let activeId = contentId;
    try {
      const decision = await fetchContentRecovery(contentId);
      const outcome = await recoverContent(contentId, decision,
        (stage) => updateProgress(activeId, { stage, error: undefined, recovery: undefined }),
        async (replacementId) => {
          activeId = replacementId;
          const refreshed = await fetchBatchV1(result.batch.batch_id);
          setResult((current) => current ? { ...current, ...refreshed } : refreshed);
          setProgress((current) => {
            const next = { ...current };
            delete next[contentId];
            return next;
          });
        });
      updateProgress(outcome.content_id, { stage: "REVIEWABLE", revisionId: outcome.revision_id, recovery: undefined });
    } catch (reason) {
      const recovery = await fetchContentRecovery(activeId).catch(() => undefined);
      updateProgress(activeId, { stage: "FAILED", error: reason instanceof Error ? reason.message : "Recovery unavailable", recovery });
    } finally {
      setProducing(false);
    }
  }

  async function refreshPiece(contentId: string) {
    try {
      const recovery = await fetchContentRecovery(contentId);
      updateProgress(contentId, { stage: "FAILED", recovery, error: recovery.safe_message });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Recovery state unavailable");
    }
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
      window.history.replaceState(null, "", `/create?batch=${encodeURIComponent(planned.batch.batch_id)}`);
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
        {result.creative_source === "deterministic_demo" && <div className={styles.productionGate} data-testid="r4-demo-mode-notice"><div><strong>Simulation mode · deterministic fixtures</strong><span>This run proves workflow, QA, approval and persistence. It does not represent production content quality. Set PRODAGENTIC_DEMO_MODE=false with a valid GEMINI_API_KEY to exercise R4 creative production.</span></div></div>}
        {result.creative_source === "model_router" && <div className={styles.signal} data-testid="r4-real-creative-source"><span aria-hidden="true" />R4 model-backed creative planning</div>}
        <div className={styles.resultHeader}>
          <div><span className={styles.kicker}>Batch planned</span><h2>{result.batch.selected_size} of {result.batch.requested_size} ideas committed</h2><p>{result.batch.selected_size < result.batch.requested_size ? "We returned fewer ideas instead of repeating recent content." : "Freshness and current-batch diversity gates passed."}</p></div>
          <div className={styles.metrics}><div><small>Memory</small><strong>{result.memory_count}</strong></div><div><small>Pool</small><strong>{result.batch.summary_counts.candidates_generated}</strong></div><div><small>Blocked</small><strong>{result.batch.summary_counts.candidates_blocked + result.batch.summary_counts.candidates_rewrite}</strong></div></div>
        </div>
        {result.batch.shortfall_reason && <div className={styles.shortfall}>{result.batch.shortfall_reason}</div>}
        {productionGate && <div className={styles.productionGate}><div><strong>Production is paused truthfully.</strong><span>{productionGate}</span></div><button onClick={() => void produceBatch(result, true)} disabled={producing}>Retry production</button></div>}

        <div className={styles.cards}>
          {result.content_items.map((item) => {
            const plan = result.plans.find((entry) => entry.content_id === item.content_id);
            const evaluation = selectedEvaluations.find((entry) => entry.candidate.candidate_id === plan?.plan.candidate_id);
            const state = progress[item.content_id];
            return <article key={item.content_id} className={styles.card} data-production-state={state?.stage || "PLANNED"}>
              <div className={styles.cardMeta}><span>{item.role}</span><span>{item.format.replace("_", " ")}</span></div>
              <h3>{item.canonical_topic.replaceAll(".", " ")}</h3><p>{item.angle}</p>
              {state && <div className={styles.progressRow}><span className={styles.progressDot} aria-hidden="true" /><strong>{stageLabel(state.stage)}</strong>{state.error && <small>{state.error}</small>}</div>}
              {state?.recovery && <div className={styles.recovery}>
                <p>{state.recovery.safe_message}</p>
                {["RETRY_PRODUCTION", "REPLAN_CONTENT", "RESUME_PIPELINE"].includes(state.recovery.action) &&
                  <button disabled={producing || busy} onClick={() => void recoverPiece(item.content_id)}>
                    {state.recovery.action === "RETRY_PRODUCTION" ? "Retry production" : state.recovery.action === "REPLAN_CONTENT" ? "Replace this idea" : "Continue saved draft"}
                  </button>}
                <details><summary>View reason</summary><p>{state.recovery.code} · {state.recovery.stage}</p></details>
              </div>}
              {state?.stage === "FAILED" && !state.recovery && <button disabled={producing} onClick={() => void refreshPiece(item.content_id)}>Reload recovery options</button>}
              {item.editorial_state === "PLANNED" && state?.stage === "WAITING" && !producing && <button disabled={busy} onClick={() => void produceBatch({ ...result, content_items: [item] }, true)}>Produce this idea</button>}
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
