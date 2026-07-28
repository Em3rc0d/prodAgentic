"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { fetchIdeas, createPipelineStream } from "@/lib/api";

/* ─── Types ─────────────────────────────────────────────────────────────── */
type Style = "educational" | "storytelling" | "controversial";
type StageKey = "research" | "write" | "edit";
type AppMode =
  | "idle"
  | "loading_ideas"
  | "ideas_ready"
  | "pipeline_running"
  | "pipeline_done";

type StageStatus = "pending" | "running" | "done";

const PIPELINE_STAGES: { key: StageKey; label: string; emoji: string }[] = [
  { key: "research", label: "Research Agent", emoji: "🔎" },
  { key: "write", label: "Content Writer", emoji: "✍️" },
  { key: "edit", label: "Editor Agent", emoji: "🧪" },
];

const STYLE_OPTIONS: { value: Style; label: string; icon: string; desc: string }[] = [
  { value: "educational", label: "Educational", icon: "📚", desc: "Teach something" },
  { value: "storytelling", label: "Storytelling", icon: "🎭", desc: "Personal story" },
  { value: "controversial", label: "Controversial", icon: "⚡", desc: "Strong take" },
];

const TOPIC_PRESETS = [
  "Spring Boot", "Kafka", "MongoDB", "Telecom", "AI aplicado",
  "Microservices", "System Design",
];

/* ─── Main Page ─────────────────────────────────────────────────────────── */
export default function Home() {
  // Controls
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState<Style>("educational");

  // App state
  const [mode, setMode] = useState<AppMode>("idle");
  const [ideas, setIdeas] = useState<string[]>([]);
  const [selectedIdea, setSelectedIdea] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Pipeline state
  const [stageStatus, setStageStatus] = useState<Record<StageKey, StageStatus>>({
    research: "pending",
    write: "pending",
    edit: "pending",
  });
  const [stageOutputs, setStageOutputs] = useState<Record<StageKey, string>>({
    research: "",
    write: "",
    edit: "",
  });
  const [stageModels, setStageModels] = useState<Record<StageKey, string | null>>({
    research: null,
    write: null,
    edit: null,
  });
  const [currentStage, setCurrentStage] = useState<StageKey | null>(null);
  const [finalPost, setFinalPost] = useState("");
  const [copied, setCopied] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  
  const activeAttemptByStage = useRef<Record<StageKey, string | null>>({
    research: null,
    write: null,
    edit: null,
  });
  const lastSequenceByAttempt = useRef<Record<string, number>>({});

  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
      }
    };
  }, []);

  /* ─── Generate Ideas ─────────────────────────────────────────────── */
  const handleGenerateIdeas = useCallback(async () => {
    if (!topic.trim()) return;
    setError(null);
    setMode("loading_ideas");
    setIdeas([]);
    setSelectedIdea(null);
    setFinalPost("");
    resetPipeline();

    try {
      const result = await fetchIdeas(topic.trim(), style);
      setIdeas(result);
      setMode("ideas_ready");
    } catch (e) {
      setError("Failed to generate ideas. Is the backend running on :8000?");
      setMode("idle");
    }
  }, [topic, style]);

  /* ─── Select Idea → Run Pipeline ────────────────────────────────── */
  const handleSelectIdea = useCallback(
    (idea: string) => {
      if (mode === "pipeline_running") return;
      setSelectedIdea(idea);
      setMode("pipeline_running");
      resetPipeline();

      if (esRef.current) esRef.current.close();
      const es = createPipelineStream(idea, topic, style);
      esRef.current = es;

      es.onmessage = (e: MessageEvent) => {
        try {
          const msg = JSON.parse(e.data);

          if (msg.stage === "stage_start" || msg.stage === "stage.attempt_started") {
            const sKey = msg.stage_name as StageKey;
            setCurrentStage(sKey);
            setStageStatus((prev) => ({ ...prev, [sKey]: "running" }));
            
            const attemptId = msg.attempt_id;
            if (attemptId) {
                activeAttemptByStage.current[sKey] = attemptId;
                lastSequenceByAttempt.current[attemptId] = 0;
            }

            if (msg.selected_model) {
              setStageModels((prev) => ({ ...prev, [sKey]: msg.selected_model }));
            }
          } else if (msg.stage === "stage.attempt_reset") {
            const sKey = msg.stage_name as StageKey;
            activeAttemptByStage.current[sKey] = null;
            setStageOutputs((prev) => ({ ...prev, [sKey]: "" }));
          } else if (msg.stage === "chunk" || msg.stage === "stage.chunk") {
            const sKey = msg.stage_name as StageKey;
            const attemptId = msg.attempt_id;
            const seq = msg.event_sequence || 0;
            
            if (attemptId && activeAttemptByStage.current[sKey] !== attemptId) return;
            if (attemptId && seq > 0) {
                if (seq <= (lastSequenceByAttempt.current[attemptId] || 0)) return;
                lastSequenceByAttempt.current[attemptId] = seq;
            }
            
            setStageOutputs((prev) => ({
              ...prev,
              [sKey]: prev[sKey] + msg.text,
            }));
          } else if (msg.stage === "stage_done" || msg.stage === "stage.completed") {
            const sKey = msg.stage_name as StageKey;
            setStageStatus((prev) => ({ ...prev, [sKey]: "done" }));
          } else if (msg.stage === "stage_failed" || msg.stage === "stage.failed") {
            setError(msg.reason || "Pipeline encountered a terminal error");
            setMode("ideas_ready");
            es.close();
          } else if (msg.stage === "complete") {
            setFinalPost(msg.final_post || "");
            setMode("pipeline_done");
            setCurrentStage(null);
            es.close();
          } else if (msg.stage === "end") {
            es.close();
          }
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        setError("Pipeline stream interrupted. Check backend logs.");
        setMode("ideas_ready");
        es.close();
      };
    },
    [topic, style, mode]
  );

  /* ─── Helpers ────────────────────────────────────────────────────── */
  function resetPipeline() {
    setStageStatus({ research: "pending", write: "pending", edit: "pending" });
    setStageOutputs({ research: "", write: "", edit: "" });
    setStageModels({ research: null, write: null, edit: null });
    setCurrentStage(null);
    setFinalPost("");
    
    activeAttemptByStage.current = { research: null, write: null, edit: null };
    lastSequenceByAttempt.current = {};
  }

  function handleCopy() {
    navigator.clipboard.writeText(finalPost).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  }

  function handleReset() {
    if (esRef.current) esRef.current.close();
    setMode("idle");
    setIdeas([]);
    setSelectedIdea(null);
    setError(null);
    setFinalPost("");
    resetPipeline();
  }

  const wordCount = finalPost
    ? finalPost.trim().split(/\s+/).filter(Boolean).length
    : 0;

  const isRunning = mode === "pipeline_running" || mode === "loading_ideas";

  return (
    <div className="app-shell">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-brand">
          <div className="header-logo">⚡</div>
          <span className="header-title">AI Content Engine</span>
          <span className="header-subtitle">LinkedIn Pipeline</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="header-model-badge">
            <div className="model-dot" />
            Gemini Model Router
          </div>
          {mode !== "idle" && (
            <button
              className="history-tab-btn"
              onClick={handleReset}
              style={{ marginLeft: 4 }}
            >
              ↩ Reset
            </button>
          )}
        </div>
      </header>

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="sidebar">
        {/* Topic input */}
        <div className="input-group">
          <p className="sidebar-section-label">Topic</p>
          <input
            id="topic-input"
            className="topic-input"
            type="text"
            placeholder="e.g. Kafka, Spring Boot..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleGenerateIdeas()}
            disabled={isRunning}
          />
          {/* Preset chips */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
            {TOPIC_PRESETS.map((t) => (
              <button
                key={t}
                onClick={() => setTopic(t)}
                disabled={isRunning}
                style={{
                  padding: "3px 9px",
                  background: topic === t ? "var(--surface-active)" : "var(--surface)",
                  border: `1px solid ${topic === t ? "var(--border-active)" : "var(--border)"}`,
                  borderRadius: 20,
                  color: topic === t ? "var(--accent-light)" : "var(--text-3)",
                  fontSize: 11,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.15s",
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Style selector */}
        <div className="input-group">
          <p className="sidebar-section-label">Style</p>
          <div className="style-pills">
            {STYLE_OPTIONS.map((s) => (
              <button
                key={s.value}
                id={`style-${s.value}`}
                className={`style-pill ${style === s.value ? "active" : ""}`}
                onClick={() => setStyle(s.value)}
                disabled={isRunning}
              >
                <span className="style-pill-icon">{s.icon}</span>
                <span>{s.label}</span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 11,
                    color: "var(--text-3)",
                    fontStyle: "italic",
                  }}
                >
                  {s.desc}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="divider" />

        {/* Generate button */}
        <button
          id="generate-btn"
          className="btn-generate"
          onClick={handleGenerateIdeas}
          disabled={!topic.trim() || isRunning}
        >
          {mode === "loading_ideas" ? "⏳ Generating..." : "⚡ Generate Ideas"}
        </button>

        <div className="divider" />

        {/* Pipeline tracker */}
        <div>
          <p className="sidebar-section-label">Pipeline Status</p>
          <div className="pipeline-tracker">
            {/* Stage 0: Idea Generator */}
            <div
              className={`pipeline-step ${
                mode === "loading_ideas" ? "active" : ""
              }`}
            >
              <div
                className={`step-indicator ${
                  mode === "loading_ideas"
                    ? "running"
                    : ideas.length > 0
                    ? "done"
                    : "pending"
                }`}
              >
                {ideas.length > 0 ? "✓" : "1"}
              </div>
              <span
                className={`step-name ${
                  ideas.length > 0
                    ? "done"
                    : mode === "loading_ideas"
                    ? "active"
                    : ""
                }`}
              >
                🧠 Idea Generator
              </span>
            </div>

            {PIPELINE_STAGES.map((s, i) => (
              <div
                key={s.key}
                className={`pipeline-step ${
                  currentStage === s.key ? "active" : ""
                }`}
              >
                <div
                  className={`step-indicator ${stageStatus[s.key]}`}
                >
                  {stageStatus[s.key] === "done"
                    ? "✓"
                    : stageStatus[s.key] === "running"
                    ? "◉"
                    : i + 2}
                </div>
                <span
                  className={`step-name ${
                    stageStatus[s.key] === "done"
                      ? "done"
                      : stageStatus[s.key] === "running"
                      ? "active"
                      : ""
                  }`}
                >
                  {s.emoji} {s.label}
                </span>
              </div>
            ))}

            {/* Publisher */}
            <div className={`pipeline-step ${mode === "pipeline_done" ? "active" : ""}`}>
              <div className={`step-indicator ${mode === "pipeline_done" ? "done" : "pending"}`}>
                {mode === "pipeline_done" ? "✓" : "5"}
              </div>
              <span className={`step-name ${mode === "pipeline_done" ? "done" : ""}`}>
                🚀 Ready to Publish
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <main className="main-content">
        {/* Error banner */}
        {error && (
          <div
            style={{
              padding: "10px 14px",
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: "var(--radius)",
              color: "#fca5a5",
              fontSize: 13,
              animation: "fade-up 0.3s ease",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* Idle hero */}
        {mode === "idle" && (
          <div className="hero-idle">
            <div className="hero-icon">⚡</div>
            <h1 className="hero-title">AI Content Engine</h1>
            <p className="hero-desc">
              Enter a topic, pick a style, and watch 5 AI agents collaborate to
              write your next viral LinkedIn post — in real time.
            </p>
            <p className="hero-tip">
              Dynamic Model Router · Research → Write → Edit pipeline
            </p>
          </div>
        )}

        {/* Loading skeleton */}
        {mode === "loading_ideas" && (
          <div className="ideas-section">
            <div className="ideas-header">
              <span className="ideas-title">Generating ideas...</span>
              <span className="ideas-count">🧠 Working</span>
            </div>
            <div className="ideas-grid">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="skeleton"
                  style={{ height: 72, animationDelay: `${i * 0.1}s` }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Ideas grid */}
        {(mode === "ideas_ready" ||
          mode === "pipeline_running" ||
          mode === "pipeline_done") &&
          ideas.length > 0 && (
            <div className="ideas-section">
              <div className="ideas-header">
                <span className="ideas-title">
                  {mode === "ideas_ready"
                    ? "Select an idea to start the pipeline"
                    : "Idea selected"}
                </span>
                <span className="ideas-count">
                  {ideas.length} ideas · {topic}
                </span>
              </div>
              <div className="ideas-grid">
                {ideas.map((idea, i) => (
                  <button
                    key={i}
                    id={`idea-card-${i}`}
                    className={`idea-card ${
                      selectedIdea === idea ? "selected" : ""
                    }`}
                    onClick={() => handleSelectIdea(idea)}
                    disabled={mode === "pipeline_running"}
                  >
                    <div className="idea-number">#{String(i + 1).padStart(2, "0")}</div>
                    {idea}
                  </button>
                ))}
              </div>
            </div>
          )}

        {/* Pipeline streaming output */}
        {(mode === "pipeline_running" || mode === "pipeline_done") &&
          selectedIdea && (
            <div className="stream-section">
              <div
                style={{
                  padding: "10px 14px",
                  background: "var(--surface-active)",
                  border: "1px solid var(--border-active)",
                  borderRadius: "var(--radius)",
                  fontSize: 13,
                  color: "var(--accent-light)",
                  fontStyle: "italic",
                }}
              >
                💡 &quot;{selectedIdea}&quot;
              </div>

              {PIPELINE_STAGES.map((s) => {
                const status = stageStatus[s.key];
                if (status === "pending" && !stageOutputs[s.key]) return null;
                return (
                  <div key={s.key}>
                    <div
                      className={`stream-stage-header ${
                        status === "running"
                          ? "active"
                          : status === "done"
                          ? "done"
                          : ""
                      }`}
                    >
                      <span className="stage-emoji">{s.emoji}</span>
                      <span className="stage-label">{s.label}</span>
                      {status === "running" && (
                        <span className="stage-status-badge running">
                          streaming...
                        </span>
                      )}
                      {status === "done" && (
                        <span className="stage-status-badge done">✓ done</span>
                      )}
                      {stageModels[s.key] && (
                        <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-3)", verticalAlign: "middle" }}>
                          · {stageModels[s.key]}
                        </span>
                      )}
                    </div>
                    <div
                      className={`stream-output ${
                        status === "running" ? "active" : ""
                      }`}
                    >
                      {stageOutputs[s.key]}
                      {status === "running" && (
                        <span className="typing-cursor" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
      </main>

      {/* ── Preview Panel ────────────────────────────────────────────────── */}
      <aside className="preview-panel">
        <div className="preview-header">
          <span className="preview-header-title">
            <span>🔗</span> LinkedIn Preview
          </span>
          {wordCount > 0 && (
            <span className="word-count">{wordCount}w</span>
          )}
        </div>

        {!finalPost ? (
          <div className="preview-empty">
            <div className="preview-empty-icon">📝</div>
            <p>Your post will appear here</p>
            <p style={{ fontSize: 11, marginTop: 4 }}>
              Select an idea to start the pipeline
            </p>
          </div>
        ) : (
          <>
            <div className="preview-content">
              <div className="linkedin-mockup">
                {/* LinkedIn-style header */}
                <div className="linkedin-header">
                  <div className="linkedin-avatar">E</div>
                  <div>
                    <div className="linkedin-name">You</div>
                    <div className="linkedin-meta">
                      Software Engineer · Just now · 🌐
                    </div>
                  </div>
                </div>

                {/* Post body */}
                <div className="linkedin-body">{finalPost}</div>

                {/* Reactions */}
                <div className="linkedin-footer">
                  <span className="li-reaction">👍</span>
                  <span className="li-reaction">❤️</span>
                  <span className="li-reaction">💡</span>
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: 12,
                      color: "var(--text-3)",
                    }}
                  >
                    Be the first to react
                  </span>
                </div>
              </div>
            </div>

            <div className="preview-actions">
              <button
                id="copy-btn"
                className={`btn-copy ${copied ? "copied" : ""}`}
                onClick={handleCopy}
              >
                {copied ? "✅ Copied!" : "📋 Copy to Clipboard"}
              </button>
              <button
                className="btn-secondary"
                onClick={() => selectedIdea && handleSelectIdea(selectedIdea)}
                disabled={mode === "pipeline_running"}
              >
                🔄 Regenerate
              </button>
              <div className="word-count">{wordCount} words · Ready to post</div>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
