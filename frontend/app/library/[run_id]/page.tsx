"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ContentRun, editContentRun, fetchContentRun } from "@/lib/api";

const STAGE_ORDER = ["research", "write", "edit", "visual"] as const;

function statusLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function ContentRunDetailPage() {
  const params = useParams<{ run_id: string }>();
  const runId = decodeURIComponent(params.run_id);

  const [run, setRun] = useState<ContentRun | null>(null);
  const [finalContent, setFinalContent] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchContentRun(runId)
      .then((value) => {
        if (!active) return;
        setRun(value);
        setFinalContent(value.final_content ?? "");
        setVisualPrompt(value.visual_prompt ?? "");
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
  }, [runId]);

  const editable = run?.status === "TEXT_READY" || run?.status === "READY_FOR_REVIEW";

  const dirty = useMemo(() => {
    if (!run) return false;
    return finalContent !== (run.final_content ?? "") || visualPrompt !== (run.visual_prompt ?? "");
  }, [finalContent, visualPrompt, run]);

  async function handleSave() {
    if (!run || !editable || !dirty || !finalContent.trim()) return;
    setSaving(true);
    setSaveMessage(null);
    setError(null);
    try {
      const updated = await editContentRun(run.run_id, {
        final_content: finalContent,
        visual_prompt: visualPrompt,
      });
      setRun(updated);
      setFinalContent(updated.final_content ?? "");
      setVisualPrompt(updated.visual_prompt ?? "");
      setSaveMessage("Saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save ContentRun");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main style={{ minHeight: "100vh", padding: 48, background: "var(--background)", color: "var(--text-1)" }}>Loading ContentRun…</main>;
  }

  if (error && !run) {
    return (
      <main style={{ minHeight: "100vh", padding: 48, background: "var(--background)", color: "var(--text-1)" }}>
        <Link href="/library" style={{ color: "var(--text-2)" }}>← Content Library</Link>
        <p>{error}</p>
      </main>
    );
  }

  if (!run) return null;

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "var(--background)",
        color: "var(--text-1)",
        padding: "40px 24px 110px",
      }}
    >
      <div style={{ maxWidth: 1120, margin: "0 auto" }}>
        <header style={{ marginBottom: 28 }}>
          <Link href="/library" style={{ color: "var(--text-2)", textDecoration: "none", fontSize: 13 }}>
            ← Content Library
          </Link>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 20, alignItems: "flex-start", marginTop: 14 }}>
            <div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
                <span style={{ border: "1px solid var(--border)", padding: "4px 8px", borderRadius: 999, fontSize: 11 }}>
                  {statusLabel(run.status)}
                </span>
                <span style={{ color: "var(--text-3)", fontSize: 12 }}>{run.style}</span>
                <span style={{ color: "var(--text-3)", fontSize: 12 }}>Run {run.run_id.slice(0, 8)}</span>
              </div>
              <h1 style={{ margin: "0 0 8px", fontSize: 30 }}>{run.idea}</h1>
              <p style={{ margin: 0, color: "var(--text-2)" }}>{run.topic}</p>
            </div>
            <div style={{ textAlign: "right", color: "var(--text-3)", fontSize: 12 }}>
              <div>Created {formatDate(run.created_at)}</div>
              <div>Updated {formatDate(run.updated_at)}</div>
            </div>
          </div>
        </header>

        {error && (
          <div style={{ marginBottom: 18, border: "1px solid var(--border)", borderRadius: 10, padding: 12, background: "var(--surface)" }}>
            {error}
          </div>
        )}

        <section style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(280px, .6fr)", gap: 18, marginBottom: 20 }}>
          <div style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Final LinkedIn content</h2>
              <span style={{ color: editable ? "var(--text-2)" : "var(--text-3)", fontSize: 12 }}>
                {editable ? "Editable before approval" : "Immutable in this state"}
              </span>
            </div>
            <textarea
              value={finalContent}
              onChange={(event) => setFinalContent(event.target.value)}
              disabled={!editable}
              style={{
                width: "100%",
                minHeight: 360,
                resize: "vertical",
                background: "var(--surface-active)",
                color: "var(--text-1)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 14,
                fontFamily: "inherit",
                lineHeight: 1.55,
              }}
            />
          </div>

          <div style={{ display: "grid", gap: 18, alignContent: "start" }}>
            <div style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 18 }}>
              <h2 style={{ margin: "0 0 10px", fontSize: 18 }}>Visual prompt</h2>
              <textarea
                value={visualPrompt}
                onChange={(event) => setVisualPrompt(event.target.value)}
                disabled={!editable}
                placeholder="No visual prompt persisted"
                style={{
                  width: "100%",
                  minHeight: 170,
                  resize: "vertical",
                  background: "var(--surface-active)",
                  color: "var(--text-1)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: 12,
                  fontFamily: "inherit",
                }}
              />
            </div>

            <div style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 18 }}>
              <h2 style={{ margin: "0 0 10px", fontSize: 18 }}>Run context</h2>
              <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 12px", fontSize: 13 }}>
                <dt style={{ color: "var(--text-3)" }}>Target</dt><dd style={{ margin: 0 }}>{run.resolved_target_language ?? "—"}</dd>
                <dt style={{ color: "var(--text-3)" }}>Image</dt><dd style={{ margin: 0 }}>{run.image_prompt_language ?? "—"}</dd>
                <dt style={{ color: "var(--text-3)" }}>Final status</dt><dd style={{ margin: 0 }}>{run.final_status ?? "—"}</dd>
                <dt style={{ color: "var(--text-3)" }}>Post projection</dt><dd style={{ margin: 0 }}>{run.post_id ?? "—"}</dd>
              </dl>
            </div>
          </div>
        </section>

        {editable && (
          <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginBottom: 28 }}>
            {saveMessage && <span style={{ color: "var(--text-2)", fontSize: 13 }}>{saveMessage}</span>}
            <button
              onClick={handleSave}
              disabled={!dirty || saving || !finalContent.trim()}
              style={{
                border: "1px solid var(--border-active)",
                borderRadius: 8,
                padding: "10px 16px",
                background: "var(--surface-active)",
                color: "var(--text-1)",
                cursor: !dirty || saving || !finalContent.trim() ? "not-allowed" : "pointer",
                opacity: !dirty || saving || !finalContent.trim() ? 0.55 : 1,
              }}
            >
              {saving ? "Saving…" : "Save review edits"}
            </button>
          </div>
        )}

        <section>
          <h2 style={{ fontSize: 20, marginBottom: 12 }}>Generation lineage</h2>
          <div style={{ display: "grid", gap: 12 }}>
            {STAGE_ORDER.map((stageName) => {
              const stage = run.stages?.[stageName];
              if (!stage) return null;
              return (
                <article key={stageName} style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", marginBottom: 10 }}>
                    <div>
                      <strong style={{ textTransform: "capitalize" }}>{stageName}</strong>
                      <span style={{ marginLeft: 10, color: "var(--text-3)", fontSize: 12 }}>{stage.status}</span>
                    </div>
                    <div style={{ color: "var(--text-3)", fontSize: 12, textAlign: "right" }}>
                      <div>{stage.provider ?? "—"} · {stage.selected_model ?? "—"}</div>
                      <div>{stage.attempt_failures ?? 0} failed attempts</div>
                    </div>
                  </div>
                  {stage.last_error && <p style={{ color: "var(--text-2)", fontSize: 12 }}>{stage.last_error}</p>}
                  <pre
                    style={{
                      margin: 0,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      background: "var(--surface-active)",
                      borderRadius: 8,
                      padding: 12,
                      color: "var(--text-2)",
                      fontFamily: "inherit",
                      fontSize: 13,
                      lineHeight: 1.5,
                    }}
                  >
                    {stage.output || "No persisted output"}
                  </pre>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}
