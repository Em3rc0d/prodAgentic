"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approveContentRun,
  ContentRun,
  editContentRun,
  fetchContentRun,
  renderVisual,
  resolveBackendAssetUrl,
} from "@/lib/api";

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

function shortDigest(value?: string | null) {
  if (!value) return "—";
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

export default function ContentRunDetailPage() {
  const params = useParams<{ run_id: string }>();
  const runId = decodeURIComponent(params.run_id);

  const [run, setRun] = useState<ContentRun | null>(null);
  const [finalContent, setFinalContent] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [renderRatio, setRenderRatio] = useState("16:9");
  const [renderStyle, setRenderStyle] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [approving, setApproving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hydrate = useCallback((value: ContentRun) => {
    setRun(value);
    setFinalContent(value.final_content ?? "");
    setVisualPrompt(value.visual_prompt ?? "");
    if (value.visual_render?.aspect_ratio) setRenderRatio(value.visual_render.aspect_ratio);
    if (value.visual_render?.style !== undefined) setRenderStyle(value.visual_render.style);
  }, []);

  useEffect(() => {
    let active = true;
    fetchContentRun(runId)
      .then((value) => {
        if (active) hydrate(value);
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
  }, [hydrate, runId]);

  const editable = run?.status === "TEXT_READY" || run?.status === "READY_FOR_REVIEW";

  const dirty = useMemo(() => {
    if (!run) return false;
    return finalContent !== (run.final_content ?? "") || visualPrompt !== (run.visual_prompt ?? "");
  }, [finalContent, visualPrompt, run]);

  const persistedAssetUrl = resolveBackendAssetUrl(run?.visual_render?.asset_url);
  const persistedRenderReady = run?.visual_render?.status === "READY" && Boolean(persistedAssetUrl);
  const approvalVisualReady = persistedRenderReady && Boolean(run?.visual_render?.asset_sha256);
  const interactionBusy = saving || rendering || approving;

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
      hydrate(updated);
      setSaveMessage("Saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save ContentRun");
    } finally {
      setSaving(false);
    }
  }

  async function handleRender() {
    if (!run || !editable || !visualPrompt.trim()) return;
    setRendering(true);
    setSaveMessage(null);
    setError(null);
    try {
      let current = run;
      if (dirty) {
        current = await editContentRun(run.run_id, {
          final_content: finalContent,
          visual_prompt: visualPrompt,
        });
        hydrate(current);
      }

      const intentId = `library-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      await renderVisual(
        visualPrompt,
        renderRatio,
        renderStyle,
        current.run_id,
        `${current.run_id}-${intentId}`
      );

      const refreshed = await fetchContentRun(current.run_id);
      hydrate(refreshed);
      setSaveMessage(refreshed.visual_render?.status === "READY" ? "Visual rendered and attached" : "Render attempt saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to render visual");
    } finally {
      setRendering(false);
    }
  }

  async function handleApprove(includeVisual: boolean) {
    if (!run || run.status !== "READY_FOR_REVIEW" || dirty || interactionBusy) return;
    setApproving(true);
    setSaveMessage(null);
    setError(null);
    try {
      const updated = await approveContentRun(run.run_id, includeVisual);
      hydrate(updated);
      setSaveMessage(includeVisual ? "Approved: text + visual locked" : "Approved: text-only bundle locked");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve ContentRun");
    } finally {
      setApproving(false);
    }
  }

  if (loading) {
    return <main style={{ height: "100vh", overflowY: "auto", padding: 48, background: "var(--bg-0)", color: "var(--text-1)" }}>Loading ContentRun…</main>;
  }

  if (error && !run) {
    return (
      <main style={{ height: "100vh", overflowY: "auto", padding: 48, background: "var(--bg-0)", color: "var(--text-1)" }}>
        <Link href="/library" style={{ color: "var(--text-2)" }}>← Content Library</Link>
        <p>{error}</p>
      </main>
    );
  }

  if (!run) return null;

  return (
    <main
      style={{
        height: "100vh",
        overflowY: "auto",
        background: "var(--bg-0)",
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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 10 }}>
                <h2 style={{ margin: 0, fontSize: 18 }}>Visual artifact</h2>
                <span style={{ color: "var(--text-3)", fontSize: 11 }}>
                  {run.visual_render ? run.visual_render.status : "NO RENDER"}
                </span>
              </div>

              {persistedRenderReady && persistedAssetUrl ? (
                <div style={{ marginBottom: 14 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={persistedAssetUrl}
                    alt={run.visual_render?.prompt_used || visualPrompt || "Generated visual"}
                    style={{ width: "100%", display: "block", borderRadius: 8, border: "1px solid var(--border)" }}
                  />
                </div>
              ) : run.visual_render?.status === "FAILED" ? (
                <div style={{ marginBottom: 14, padding: 12, borderRadius: 8, background: "var(--surface-active)", color: "var(--text-2)", fontSize: 12 }}>
                  Last render failed{run.visual_render.error_message ? `: ${run.visual_render.error_message}` : "."}
                </div>
              ) : (
                <div style={{ marginBottom: 14, padding: 12, borderRadius: 8, border: "1px dashed var(--border)", color: "var(--text-3)", fontSize: 12 }}>
                  No current rendered artifact. Approval cannot treat a stale image as current evidence.
                </div>
              )}

              <textarea
                value={visualPrompt}
                onChange={(event) => setVisualPrompt(event.target.value)}
                disabled={!editable}
                placeholder="No visual prompt persisted"
                style={{
                  width: "100%",
                  minHeight: 150,
                  resize: "vertical",
                  background: "var(--surface-active)",
                  color: "var(--text-1)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: 12,
                  fontFamily: "inherit",
                  marginBottom: 12,
                }}
              />

              {editable && (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
                    <select
                      aria-label="Visual aspect ratio"
                      value={renderRatio}
                      onChange={(event) => setRenderRatio(event.target.value)}
                      style={{ background: "var(--surface-active)", color: "var(--text-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 9 }}
                    >
                      <option value="16:9">16:9</option>
                      <option value="1:1">1:1</option>
                      <option value="4:5">4:5</option>
                    </select>
                    <select
                      aria-label="Visual style"
                      value={renderStyle}
                      onChange={(event) => setRenderStyle(event.target.value)}
                      style={{ background: "var(--surface-active)", color: "var(--text-1)", border: "1px solid var(--border)", borderRadius: 8, padding: 9 }}
                    >
                      <option value="">Default</option>
                      <option value="technical_editorial">Technical Editorial</option>
                      <option value="cinematic">Cinematic</option>
                      <option value="minimal">Minimal</option>
                      <option value="illustration">Illustration</option>
                      <option value="photorealistic">Photorealistic</option>
                    </select>
                  </div>
                  <button
                    onClick={handleRender}
                    disabled={interactionBusy || !visualPrompt.trim() || !finalContent.trim()}
                    style={{
                      width: "100%",
                      border: "1px solid var(--border-active)",
                      borderRadius: 8,
                      padding: "10px 12px",
                      background: "var(--surface-active)",
                      color: "var(--text-1)",
                      cursor: interactionBusy || !visualPrompt.trim() || !finalContent.trim() ? "not-allowed" : "pointer",
                      opacity: interactionBusy || !visualPrompt.trim() || !finalContent.trim() ? 0.55 : 1,
                    }}
                  >
                    {rendering ? "Rendering…" : persistedRenderReady ? "Render replacement" : "Render image"}
                  </button>
                </>
              )}

              {run.visual_render && (
                <dl style={{ margin: "12px 0 0", display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 10px", fontSize: 11, color: "var(--text-3)" }}>
                  <dt>Provider</dt><dd style={{ margin: 0 }}>{run.visual_render.provider}</dd>
                  <dt>Ratio</dt><dd style={{ margin: 0 }}>{run.visual_render.aspect_ratio}</dd>
                  <dt>Style</dt><dd style={{ margin: 0 }}>{run.visual_render.style || "default"}</dd>
                  <dt>Asset hash</dt><dd style={{ margin: 0, fontFamily: "monospace" }}>{shortDigest(run.visual_render.asset_sha256)}</dd>
                  <dt>Rendered</dt><dd style={{ margin: 0 }}>{formatDate(run.visual_render.rendered_at)}</dd>
                </dl>
              )}
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
          <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginBottom: 20 }}>
            {saveMessage && <span style={{ color: "var(--text-2)", fontSize: 13 }}>{saveMessage}</span>}
            <button
              onClick={handleSave}
              disabled={!dirty || interactionBusy || !finalContent.trim()}
              style={{
                border: "1px solid var(--border-active)",
                borderRadius: 8,
                padding: "10px 16px",
                background: "var(--surface-active)",
                color: "var(--text-1)",
                cursor: !dirty || interactionBusy || !finalContent.trim() ? "not-allowed" : "pointer",
                opacity: !dirty || interactionBusy || !finalContent.trim() ? 0.55 : 1,
              }}
            >
              {saving ? "Saving…" : "Save review edits"}
            </button>
          </div>
        )}

        {run.status === "READY_FOR_REVIEW" && (
          <section style={{ border: "1px solid var(--border-active)", borderRadius: 12, background: "var(--surface)", padding: 20, marginBottom: 28 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 18, alignItems: "flex-start", flexWrap: "wrap" }}>
              <div style={{ maxWidth: 650 }}>
                <h2 style={{ margin: "0 0 8px", fontSize: 20 }}>Human approval gate</h2>
                <p style={{ margin: 0, color: "var(--text-2)", lineHeight: 1.5 }}>
                  Approval freezes the exact publishable bundle. After this transition, review edits and visual replacement are blocked.
                </p>
                {dirty && <p style={{ margin: "10px 0 0", color: "var(--text-2)", fontSize: 13 }}>Save your current edits before approving.</p>}
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
                <button
                  onClick={() => handleApprove(false)}
                  disabled={dirty || interactionBusy || !finalContent.trim()}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "10px 14px",
                    background: "var(--surface-active)",
                    color: "var(--text-1)",
                    cursor: dirty || interactionBusy || !finalContent.trim() ? "not-allowed" : "pointer",
                    opacity: dirty || interactionBusy || !finalContent.trim() ? 0.55 : 1,
                  }}
                >
                  {approving ? "Approving…" : "Approve text only"}
                </button>
                <button
                  onClick={() => handleApprove(true)}
                  disabled={dirty || interactionBusy || !finalContent.trim() || !approvalVisualReady}
                  style={{
                    border: "1px solid var(--border-active)",
                    borderRadius: 8,
                    padding: "10px 14px",
                    background: "var(--surface-active)",
                    color: "var(--text-1)",
                    cursor: dirty || interactionBusy || !finalContent.trim() || !approvalVisualReady ? "not-allowed" : "pointer",
                    opacity: dirty || interactionBusy || !finalContent.trim() || !approvalVisualReady ? 0.55 : 1,
                  }}
                >
                  {approving ? "Approving…" : "Approve text + visual"}
                </button>
              </div>
            </div>
            {!approvalVisualReady && (
              <p style={{ margin: "12px 0 0", color: "var(--text-3)", fontSize: 12 }}>
                Text + visual approval requires a current READY render with an asset digest. Text-only approval remains available.
              </p>
            )}
          </section>
        )}

        {run.approval && (
          <section style={{ border: "1px solid var(--border)", borderRadius: 12, background: "var(--surface)", padding: 20, marginBottom: 28 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 18, flexWrap: "wrap" }}>
              <div>
                <h2 style={{ margin: "0 0 6px", fontSize: 20 }}>Approved publishable bundle</h2>
                <p style={{ margin: 0, color: "var(--text-2)" }}>
                  {run.approval.include_visual ? "Text + visual" : "Text only"} · {formatDate(run.approval.approved_at)}
                </p>
              </div>
              <div style={{ color: "var(--text-3)", fontSize: 12, textAlign: "right", fontFamily: "monospace" }}>
                <div>Bundle {shortDigest(run.approval.bundle_sha256)}</div>
                <div>Text {shortDigest(run.approval.final_content_sha256)}</div>
                {run.approval.visual_render_sha256 && <div>Visual {shortDigest(run.approval.visual_render_sha256)}</div>}
              </div>
            </div>
          </section>
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
