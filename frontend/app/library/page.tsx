"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ContentRun, ContentRunStatus, fetchContentRuns } from "@/lib/api";

const STATUS_ORDER: ContentRunStatus[] = [
  "READY_FOR_REVIEW",
  "TEXT_READY",
  "GENERATING",
  "FAILED",
  "APPROVED",
  "SCHEDULED",
  "PUBLISHING",
  "PUBLISHED",
  "CANCELLED",
  "ARCHIVED",
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusLabel(status: ContentRunStatus) {
  return status.replaceAll("_", " ");
}

export default function ContentLibraryPage() {
  const [runs, setRuns] = useState<ContentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ContentRunStatus | "ALL">("ALL");

  useEffect(() => {
    let active = true;
    fetchContentRuns(100)
      .then((result) => {
        if (active) setRuns(result.runs);
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const visibleRuns = useMemo(
    () => (filter === "ALL" ? runs : runs.filter((run) => run.status === filter)),
    [filter, runs]
  );

  const availableStatuses = useMemo(
    () => STATUS_ORDER.filter((status) => runs.some((run) => run.status === status)),
    [runs]
  );

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "var(--background)",
        color: "var(--text-1)",
        padding: "48px 24px 96px",
      }}
    >
      <div style={{ maxWidth: 1080, margin: "0 auto" }}>
        <header style={{ marginBottom: 28 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div>
              <p style={{ color: "var(--text-3)", margin: 0, fontSize: 13, letterSpacing: ".08em" }}>
                prodAgentic
              </p>
              <h1 style={{ fontSize: 32, margin: "6px 0 8px" }}>Content Library</h1>
              <p style={{ color: "var(--text-2)", margin: 0 }}>
                Reopen every persisted ContentRun with its full generation lineage.
              </p>
            </div>
            <Link
              href="/"
              style={{
                textDecoration: "none",
                color: "var(--text-1)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "10px 14px",
                background: "var(--surface)",
              }}
            >
              + New content
            </Link>
          </div>
        </header>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
          <button
            onClick={() => setFilter("ALL")}
            style={{
              border: "1px solid var(--border)",
              borderRadius: 999,
              padding: "7px 12px",
              background: filter === "ALL" ? "var(--surface-active)" : "var(--surface)",
              color: "var(--text-1)",
              cursor: "pointer",
            }}
          >
            All · {runs.length}
          </button>
          {availableStatuses.map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 999,
                padding: "7px 12px",
                background: filter === status ? "var(--surface-active)" : "var(--surface)",
                color: "var(--text-1)",
                cursor: "pointer",
              }}
            >
              {statusLabel(status)} · {runs.filter((run) => run.status === status).length}
            </button>
          ))}
        </div>

        {loading && <p style={{ color: "var(--text-2)" }}>Loading persisted runs…</p>}
        {error && (
          <div style={{ border: "1px solid var(--border)", background: "var(--surface)", padding: 16, borderRadius: 10 }}>
            {error}
          </div>
        )}

        {!loading && !error && visibleRuns.length === 0 && (
          <div style={{ border: "1px dashed var(--border)", borderRadius: 12, padding: 32, textAlign: "center" }}>
            <h2 style={{ marginTop: 0 }}>No ContentRuns here yet</h2>
            <p style={{ color: "var(--text-2)" }}>Generate a post and it will appear here once persistence is available.</p>
          </div>
        )}

        <div style={{ display: "grid", gap: 12 }}>
          {visibleRuns.map((run) => (
            <Link
              key={run.run_id}
              href={`/library/${encodeURIComponent(run.run_id)}`}
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <article
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  background: "var(--surface)",
                  padding: 18,
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 20,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
                    <span
                      style={{
                        fontSize: 11,
                        padding: "4px 8px",
                        borderRadius: 999,
                        border: "1px solid var(--border)",
                        color: "var(--text-2)",
                      }}
                    >
                      {statusLabel(run.status)}
                    </span>
                    <span style={{ color: "var(--text-3)", fontSize: 12 }}>{run.style}</span>
                    <span style={{ color: "var(--text-3)", fontSize: 12 }}>{run.resolved_target_language ?? "—"}</span>
                  </div>
                  <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>{run.idea}</h2>
                  <p style={{ margin: 0, color: "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {run.topic}
                  </p>
                </div>
                <div style={{ textAlign: "right", color: "var(--text-3)", fontSize: 12, whiteSpace: "nowrap" }}>
                  <div>{formatDate(run.updated_at)}</div>
                  <div style={{ marginTop: 8 }}>Open →</div>
                </div>
              </article>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
