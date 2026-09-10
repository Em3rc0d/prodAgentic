"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CalendarEntry,
  CalendarPayload,
  connectLinkedIn,
  createSchedule,
  disconnectLinkedIn,
  downloadManualExport,
  fetchCalendar,
  reconcilePublication,
} from "@/lib/calendar";
import { mk1PublishingEnabled } from "@/lib/mk1-feature-flags";
import styles from "./calendar.module.css";

type ViewMode = "week" | "month" | "queue";

const statusLabels: Record<string, string> = {
  APPROVED_UNSCHEDULED: "Approved · unscheduled",
  SCHEDULED: "Scheduled",
  DISPATCHED: "Queued for publishing",
  PENDING: "Waiting for worker",
  PUBLISHING: "Publishing",
  PUBLISHED: "Published",
  FAILED_SAFE: "Not published · safe failure",
  RECONCILIATION_REQUIRED: "Needs reconciliation",
  CANCELLED: "Cancelled",
  FAILED: "Failed",
  COMPLETED: "Published",
};

function stateLabel(state: string) {
  return statusLabels[state] || state.replaceAll("_", " ");
}

function localDate(value?: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function visibleByMode(entry: CalendarEntry, mode: ViewMode) {
  if (mode === "queue") return true;
  if (!entry.scheduled_for) return true;
  const now = Date.now();
  const delta = new Date(entry.scheduled_for).getTime() - now;
  const horizon = mode === "week" ? 8 * 24 * 60 * 60 * 1000 : 36 * 24 * 60 * 60 * 1000;
  return delta >= -24 * 60 * 60 * 1000 && delta <= horizon;
}

export default function CalendarPage() {
  const [payload, setPayload] = useState<CalendarPayload | null>(null);
  const [mode, setMode] = useState<ViewMode>("week");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [scheduleApproval, setScheduleApproval] = useState<string | null>(null);
  const [localTime, setLocalTime] = useState("");

  const timezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    [],
  );

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setPayload(await fetchCalendar());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calendar could not be loaded");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (mk1PublishingEnabled) void refresh();
  }, []);

  const entries = useMemo(
    () => (payload?.entries || []).filter((entry) => visibleByMode(entry, mode)),
    [payload, mode],
  );

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  async function submitSchedule() {
    if (!scheduleApproval || !localTime) return;
    const instant = new Date(localTime);
    if (Number.isNaN(instant.getTime())) {
      setError("Choose a valid local date and time.");
      return;
    }
    await run(`schedule-${scheduleApproval}`, async () => {
      await createSchedule(scheduleApproval, instant.toISOString(), timezone);
      setScheduleApproval(null);
      setLocalTime("");
    });
  }

  if (!mk1PublishingEnabled) {
    return (
      <main className={styles.page} data-testid="s10-calendar">
        <section className={styles.emptyState}>
          <span className={styles.eyebrow}>Distribution</span>
          <h1>Calendar is not enabled for this rollout.</h1>
          <p>Approved content remains available through Manual Export while the publishing surface is disabled.</p>
        </section>
      </main>
    );
  }

  return (
    <main className={styles.page} data-testid="s10-calendar" data-view={mode}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>Distribution control</span>
          <h1>Calendar</h1>
          <p>Schedule only approved authority. Provider uncertainty stays visible instead of being retried blindly.</p>
        </div>
        <div className={styles.connectionCard} data-connected={payload?.capability.connected ? "true" : "false"}>
          <span className={styles.connectionDot} aria-hidden="true" />
          <div>
            <strong>{payload?.capability.connected ? "LinkedIn connected" : "LinkedIn not ready"}</strong>
            <small>{payload?.capability.reason || (payload?.capability.api_version ? `API ${payload.capability.api_version}` : "Automatic publishing capability")}</small>
          </div>
          {payload?.capability.connected ? (
            <button className={styles.ghostButton} onClick={() => run("disconnect", disconnectLinkedIn)} disabled={busy === "disconnect"}>
              Disconnect
            </button>
          ) : (
            <button className={styles.primaryButton} onClick={() => run("connect", connectLinkedIn)} disabled={busy === "connect"}>
              Connect LinkedIn
            </button>
          )}
        </div>
      </header>

      <section className={styles.toolbar} aria-label="Calendar views">
        <div className={styles.segmented} role="group" aria-label="Calendar view">
          {(["week", "month", "queue"] as ViewMode[]).map((item) => (
            <button
              key={item}
              aria-pressed={mode === item}
              className={mode === item ? styles.activeView : undefined}
              onClick={() => setMode(item)}
            >
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>
        <button className={styles.ghostButton} onClick={() => void refresh()} disabled={loading}>
          Refresh
        </button>
      </section>

      {error && <div className={styles.error} role="alert">{error}</div>}

      <section className={styles.board} aria-live="polite">
        {loading ? (
          <div className={styles.emptyState}>Loading distribution authority…</div>
        ) : entries.length === 0 ? (
          <div className={styles.emptyState}>
            <h2>No distribution work in this view.</h2>
            <p>Approved content will appear here as soon as it has authority to be scheduled or exported.</p>
          </div>
        ) : (
          entries.map((entry) => (
            <article key={`${entry.kind}-${entry.schedule_id || entry.approval_id}`} className={styles.entry} data-state={entry.state}>
              <div className={styles.entryTop}>
                <div>
                  <span className={styles.kind}>{entry.kind === "approval" ? "APPROVAL" : "LINKEDIN"}</span>
                  <h2>{entry.content_id || entry.approval_id}</h2>
                </div>
                <span className={styles.status} data-status={entry.state}>
                  <span aria-hidden="true">●</span> {stateLabel(entry.state)}
                </span>
              </div>

              <dl className={styles.meta}>
                <div><dt>When</dt><dd>{localDate(entry.scheduled_for || entry.approved_at)}</dd></div>
                <div><dt>Timezone</dt><dd>{entry.timezone_context || timezone}</dd></div>
                <div><dt>Authority</dt><dd>{entry.approval_id}</dd></div>
              </dl>

              {(entry.reconciliation_reason || entry.safe_error) && (
                <details className={styles.details}>
                  <summary>Provider / evidence detail</summary>
                  <p>{entry.reconciliation_reason || entry.safe_error}</p>
                </details>
              )}

              <div className={styles.actions}>
                {entry.kind === "approval" && payload?.capability.can_publish && (
                  <button className={styles.primaryButton} onClick={() => setScheduleApproval(entry.approval_id)}>
                    Schedule on LinkedIn
                  </button>
                )}
                {entry.kind === "approval" && payload?.manual_export_fallback && (
                  <button
                    className={styles.ghostButton}
                    onClick={() => run(`export-${entry.approval_id}`, () => downloadManualExport(entry.approval_id))}
                    disabled={busy === `export-${entry.approval_id}`}
                  >
                    Download manual package
                  </button>
                )}
                {entry.state === "RECONCILIATION_REQUIRED" && entry.publication_id && (
                  <button
                    className={styles.warningButton}
                    onClick={() => run(`reconcile-${entry.publication_id}`, () => reconcilePublication(entry.publication_id!))}
                    disabled={busy === `reconcile-${entry.publication_id}`}
                  >
                    Reconcile evidence
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </section>

      {scheduleApproval && (
        <div className={styles.scrim} role="presentation" onMouseDown={() => setScheduleApproval(null)}>
          <section
            className={styles.dialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby="schedule-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <span className={styles.eyebrow}>LinkedIn schedule</span>
            <h2 id="schedule-title">Choose the local publishing time</h2>
            <p>The browser timezone is stored with the schedule so the UI can explain the original intent later.</p>
            <label>
              Local date and time
              <input
                type="datetime-local"
                value={localTime}
                onChange={(event) => setLocalTime(event.target.value)}
                autoFocus
              />
            </label>
            <div className={styles.timezone}>Timezone · <strong>{timezone}</strong></div>
            <div className={styles.dialogActions}>
              <button className={styles.ghostButton} onClick={() => setScheduleApproval(null)}>Cancel</button>
              <button
                className={styles.primaryButton}
                onClick={() => void submitSchedule()}
                disabled={!localTime || busy === `schedule-${scheduleApproval}`}
              >
                Schedule approved content
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
