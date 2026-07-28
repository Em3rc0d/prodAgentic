import os

content = """\"use client\";

import { useState, useRef, useCallback, useEffect } from "react";
import { fetchIdeas, createPipelineStream } from "@/lib/api";
import { AgentActivityIndicator } from "@/components/AgentActivityIndicator";

type Style = "educational" | "storytelling" | "controversial";
type StageKey = "research" | "write" | "edit" | "visual";
type AppMode = "idle" | "loading_ideas" | "ideas_ready" | "pipeline_running" | "pipeline_done";
type StageStatus = "pending" | "running" | "done" | "failed";
type TabId = "brief" | "content" | "visuals";

const PIPELINE_STAGES: { key: StageKey; label: string; emoji: string }[] = [
  { key: "research", label: "Research Agent", emoji: "🔎" },
  { key: "write", label: "Content Writer", emoji: "✍️" },
  { key: "edit", label: "Editor Agent", emoji: "🧪" },
  { key: "visual", label: "Visual Agent", emoji: "🎨" },
];

const STYLE_OPTIONS: { value: Style; label: string; icon: string; desc: string }[] = [
  { value: "educational", label: "Educational", icon: "📚", desc: "Teach something" },
  { value: "storytelling", label: "Storytelling", icon: "🎭", desc: "Personal story" },
  { value: "controversial", label: "Controversial", icon: "⚡", desc: "Strong take" },
];

const TOPIC_PRESETS = [
  "Spring Boot", "Kafka", "MongoDB", "Telecom", "AI aplicado", "Microservices", "System Design",
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>("brief");

  // Controls
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState<Style>("educational");
  const [targetLanguage, setTargetLanguage] = useState<string>("es");
  const [imagePromptLanguage, setImagePromptLanguage] = useState<string>("en");

  // App state
  const [mode, setMode] = useState<AppMode>("idle");
  const [ideas, setIdeas] = useState<string[]>([]);
  const [selectedIdea, setSelectedIdea] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Pipeline state
  const [stageStatus, setStageStatus] = useState<Record<StageKey, StageStatus>>({
    research: "pending", write: "pending", edit: "pending", visual: "pending",
  });
  const [stageOutputs, setStageOutputs] = useState<Record<StageKey, string>>({
    research: "", write: "", edit: "", visual: "",
  });
  const [stageModels, setStageModels] = useState<Record<StageKey, string | null>>({
    research: null, write: null, edit: null, visual: null,
  });
  const [currentStage, setCurrentStage] = useState<StageKey | null>(null);
  const [finalPost, setFinalPost] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [copied, setCopied] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const activeAttemptByStage = useRef<Record<StageKey, string | null>>({
    research: null, write: null, edit: null, visual: null,
  });
  const lastSequenceByAttempt = useRef<Record<string, number>>({});

  useEffect(() => {
    return () => { if (esRef.current) esRef.current.close(); };
  }, []);

  const handleGenerateIdeas = useCallback(async () => {
    if (!topic.trim()) return;
    setError(null); setMode("loading_ideas"); setIdeas([]); setSelectedIdea(null);
    setFinalPost(""); setVisualPrompt(""); resetPipeline();

    try {
      const result = await fetchIdeas(topic.trim(), style, targetLanguage);
      setIdeas(result);
      setMode("ideas_ready");
    } catch (e) {
      setError("Failed to generate ideas. Is the backend running on :8000?");
      setMode("idle");
    }
  }, [topic, style, targetLanguage]);

  const handleSelectIdea = useCallback((idea: string) => {
    if (mode === "pipeline_running") return;
    setSelectedIdea(idea); setMode("pipeline_running"); resetPipeline();
    setActiveTab("content"); // Switch to content tab when pipeline starts

    if (esRef.current) esRef.current.close();
    const es = createPipelineStream(idea, topic, style, targetLanguage, imagePromptLanguage);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.stage === "stage_start" || msg.stage === "stage.attempt_started") {
          const sKey = msg.stage_name as StageKey;
          setCurrentStage(sKey);
          setStageStatus((prev) => ({ ...prev, [sKey]: "running" }));
          
          if (msg.attempt_id) {
              activeAttemptByStage.current[sKey] = msg.attempt_id;
              lastSequenceByAttempt.current[msg.attempt_id] = 0;
          }
          if (msg.selected_model) setStageModels((prev) => ({ ...prev, [sKey]: msg.selected_model }));
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
          setStageOutputs((prev) => ({ ...prev, [sKey]: prev[sKey] + msg.text }));
        } else if (msg.stage === "stage_done" || msg.stage === "stage.completed") {
          setStageStatus((prev) => ({ ...prev, [msg.stage_name as StageKey]: "done" }));
        } else if (msg.stage === "stage_failed" || msg.stage === "stage.failed") {
          const rawStage = msg.stage_name;
          if (rawStage && rawStage !== "unknown") {
              setStageStatus((prev) => ({ ...prev, [rawStage as StageKey]: "failed" }));
              activeAttemptByStage.current[rawStage as StageKey] = null;
          }
          setCurrentStage(null); setMode("ideas_ready"); setFinalPost("");
          // Don't close ES if it's visual agent failure, we want to proceed.
          // Wait, backend will send complete anyway if ignore_failure=True, but 
          // wait! If backend sends stage.failed it might terminate the stream if not ignored.
          // In orchestrator, visual agent failure is ignored, and it continues to publish final post.
        } else if (msg.stage === "complete") {
          setFinalPost(msg.final_post || "");
          setVisualPrompt(msg.visual_prompt || "");
          setMode("pipeline_done"); setCurrentStage(null); es.close();
        } else if (msg.stage === "error") {
          setError(msg.reason || "Pipeline encountered a terminal error");
          setMode("ideas_ready"); setFinalPost(""); es.close();
        } else if (msg.stage === "end") {
          es.close();
        }
      } catch {}
    };
    es.onerror = () => {
      setError("Pipeline stream interrupted. Check backend logs."); setMode("ideas_ready"); es.close();
    };
  }, [topic, style, mode, targetLanguage, imagePromptLanguage]);

  function resetPipeline() {
    setStageStatus({ research: "pending", write: "pending", edit: "pending", visual: "pending" });
    setStageOutputs({ research: "", write: "", edit: "", visual: "" });
    setStageModels({ research: null, write: null, edit: null, visual: null });
    setCurrentStage(null); setFinalPost(""); setVisualPrompt("");
    activeAttemptByStage.current = { research: null, write: null, edit: null, visual: null };
    lastSequenceByAttempt.current = {};
  }

  function handleReset() {
    if (esRef.current) esRef.current.close();
    setMode("idle"); setIdeas([]); setSelectedIdea(null); setError(null); setFinalPost("");
    setActiveTab("brief"); resetPipeline();
  }

  const isRunning = mode === "pipeline_running" || mode === "loading_ideas";
  const wordCount = finalPost ? finalPost.trim().split(/\s+/).filter(Boolean).length : 0;

  return (
    <div className="app-shell tabbed-workspace">
      <header className="app-header">
        <div className="header-brand">
          <div className="header-logo">⚡</div>
          <span className="header-title">AI Content Engine</span>
        </div>
        
        <div className="workspace-tabs">
          <button className={`tab-btn ${activeTab === "brief" ? "active" : ""}`} onClick={() => setActiveTab("brief")}>
            <span className="tab-icon">📝</span> Brief & Settings
          </button>
          <button className={`tab-btn ${activeTab === "content" ? "active" : ""}`} onClick={() => setActiveTab("content")}>
            <span className="tab-icon">✍️</span> Content {mode === "pipeline_running" && currentStage !== "visual" && <AgentActivityIndicator stage={currentStage || "research"} status="running" size={20} />}
          </button>
          <button className={`tab-btn ${activeTab === "visuals" ? "active" : ""}`} onClick={() => setActiveTab("visuals")}>
            <span className="tab-icon">🎨</span> Visuals {mode === "pipeline_running" && currentStage === "visual" && <AgentActivityIndicator stage="visual" status="running" size={20} />}
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="header-model-badge"><div className="model-dot" />Gemini Router</div>
          {mode !== "idle" && <button className="history-tab-btn" onClick={handleReset} style={{ marginLeft: 4 }}>↩ Reset</button>}
        </div>
      </header>

      {error && (
        <div className="global-error-banner">⚠️ {error}</div>
      )}

      <main className="tab-content-area">
        {activeTab === "brief" && (
          <div className="tab-pane brief-pane">
            <div className="brief-sidebar">
              <div className="input-group">
                <p className="sidebar-section-label">Topic</p>
                <input id="topic-input" className="topic-input" type="text" placeholder="e.g. Kafka, Spring Boot..." value={topic} onChange={(e) => setTopic(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleGenerateIdeas()} disabled={isRunning} />
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
                  {TOPIC_PRESETS.map((t) => (
                    <button key={t} onClick={() => setTopic(t)} disabled={isRunning} className={`preset-chip ${topic === t ? 'active' : ''}`}>{t}</button>
                  ))}
                </div>
              </div>
              <div className="input-group">
                <p className="sidebar-section-label">Style</p>
                <div className="style-pills">
                  {STYLE_OPTIONS.map((s) => (
                    <button key={s.value} className={`style-pill ${style === s.value ? "active" : ""}`} onClick={() => setStyle(s.value)} disabled={isRunning}>
                      <span className="style-pill-icon">{s.icon}</span><span>{s.label}</span>
                      <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-3)", fontStyle: "italic" }}>{s.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="input-group">
                <p className="sidebar-section-label">Target Language</p>
                <select value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)} disabled={isRunning} className="language-select">
                  <option value="en">English</option><option value="es">Español</option><option value="pt">Português</option>
                </select>
              </div>
              <button id="generate-btn" className="btn-generate" onClick={handleGenerateIdeas} disabled={!topic.trim() || isRunning}>
                {mode === "loading_ideas" ? "⏳ Generating..." : "⚡ Generate Ideas"}
              </button>
            </div>
            
            <div className="brief-main">
              {mode === "idle" && (
                <div className="hero-idle">
                  <div className="hero-icon">⚡</div>
                  <h1 className="hero-title">AI Content Engine</h1>
                  <p className="hero-desc">Enter a topic, pick a style, and let AI agents craft your content.</p>
                </div>
              )}
              {mode === "loading_ideas" && (
                <div className="ideas-section">
                  <div className="ideas-header"><span className="ideas-title">Generating ideas...</span><AgentActivityIndicator stage="idea" status="running" size={20} /></div>
                  <div className="ideas-grid">{[...Array(6)].map((_, i) => (<div key={i} className="skeleton" style={{ height: 72, animationDelay: `${i * 0.1}s` }} />))}</div>
                </div>
              )}
              {(mode === "ideas_ready" || mode === "pipeline_running" || mode === "pipeline_done") && ideas.length > 0 && (
                <div className="ideas-section">
                  <div className="ideas-header">
                    <span className="ideas-title">{mode === "ideas_ready" ? "Select an idea to start the pipeline" : "Idea selected"}</span>
                    <span className="ideas-count">{ideas.length} ideas</span>
                  </div>
                  <div className="ideas-grid">
                    {ideas.map((idea, i) => (
                      <button key={i} className={`idea-card ${selectedIdea === idea ? "selected" : ""}`} onClick={() => handleSelectIdea(idea)} disabled={mode === "pipeline_running"}>
                        <div className="idea-number">#{String(i + 1).padStart(2, "0")}</div>{idea}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "content" && (
          <div className="tab-pane content-pane">
            <div className="pipeline-sidebar">
              <p className="sidebar-section-label">Pipeline Status</p>
              <div className="pipeline-tracker">
                <div className={`pipeline-step active`}><div className={`step-indicator done`}>✓</div><span className={`step-name done`}>🧠 Idea Generator</span></div>
                {PIPELINE_STAGES.filter(s => s.key !== 'visual').map((s, i) => (
                  <div key={s.key} className={`pipeline-step ${currentStage === s.key ? "active" : ""}`}>
                    <div className={`step-indicator ${stageStatus[s.key]}`}>
                      {stageStatus[s.key] === "done" ? "✓" : stageStatus[s.key] === "running" ? <AgentActivityIndicator stage={s.key} status="running" size={20} /> : i + 2}
                    </div>
                    <span className={`step-name ${stageStatus[s.key] === "done" ? "done" : stageStatus[s.key] === "failed" ? "failed" : stageStatus[s.key] === "running" ? "active" : ""}`}>{s.emoji} {s.label}</span>
                  </div>
                ))}
                <div className={`pipeline-step ${mode === "pipeline_done" ? "active" : ""}`}><div className={`step-indicator ${mode === "pipeline_done" ? "done" : "pending"}`}>{mode === "pipeline_done" ? "✓" : "5"}</div><span className={`step-name ${mode === "pipeline_done" ? "done" : ""}`}>🚀 Ready to Publish</span></div>
              </div>
            </div>
            
            <div className="content-streams">
              {!selectedIdea ? (
                <div className="empty-state">Select an idea in the Brief tab to start generation.</div>
              ) : (
                <div className="stream-section">
                  <div className="selected-idea-banner">💡 "{selectedIdea}"</div>
                  {PIPELINE_STAGES.filter(s => s.key !== 'visual').map((s) => {
                    const status = stageStatus[s.key];
                    if (status === "pending" && !stageOutputs[s.key]) return null;
                    return (
                      <div key={s.key}>
                        <div className={`stream-stage-header ${status === "running" ? "active" : status === "done" ? "done" : status === "failed" ? "failed" : ""}`}>
                          <span className="stage-emoji">{s.emoji}</span><span className="stage-label">{s.label}</span>
                          {status === "running" && <span className="stage-status-badge running">streaming...</span>}
                          {status === "done" && <span className="stage-status-badge done">✓ done</span>}
                          {status === "failed" && <span className="stage-status-badge" style={{color: "#fca5a5", background: "rgba(239,68,68,0.1)"}}>❌ failed</span>}
                          {stageModels[s.key] && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-3)" }}>· {stageModels[s.key]}</span>}
                        </div>
                        <div className={`stream-output ${status === "running" ? "active" : ""}`}>{stageOutputs[s.key]}{status === "running" && <span className="typing-cursor" />}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="content-preview">
              <div className="preview-header"><span className="preview-header-title">🔗 LinkedIn Preview</span>{wordCount > 0 && <span className="word-count">{wordCount}w</span>}</div>
              {!finalPost ? (
                <div className="preview-empty"><div className="preview-empty-icon">📝</div><p>Your post will appear here</p></div>
              ) : (
                <>
                  <div className="preview-content">
                    <div className="linkedin-mockup">
                      <div className="linkedin-header"><div className="linkedin-avatar">E</div><div><div className="linkedin-name">You</div><div className="linkedin-meta">Software Engineer · Just now · 🌐</div></div></div>
                      <div className="linkedin-body">{finalPost}</div>
                      <div className="linkedin-footer"><span className="li-reaction">👍</span><span className="li-reaction">❤️</span><span className="li-reaction">💡</span></div>
                    </div>
                  </div>
                  <div className="preview-actions">
                    <button className={`btn-copy ${copied ? "copied" : ""}`} onClick={handleCopy}>{copied ? "✅ Copied!" : "📋 Copy to Clipboard"}</button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {activeTab === "visuals" && (
          <div className="tab-pane visuals-pane">
             <div className="brief-sidebar">
                <div className="input-group">
                  <p className="sidebar-section-label">Image Prompt Language</p>
                  <select value={imagePromptLanguage} onChange={(e) => setImagePromptLanguage(e.target.value)} disabled={isRunning} className="language-select">
                    <option value="en">English</option><option value="es">Español</option><option value="pt">Português</option>
                  </select>
                </div>
             </div>
             <div className="visuals-main">
                <div className="stream-section">
                    <div className={`stream-stage-header ${stageStatus.visual === "running" ? "active" : stageStatus.visual === "done" ? "done" : stageStatus.visual === "failed" ? "failed" : ""}`}>
                        <span className="stage-emoji">🎨</span><span className="stage-label">Visual Agent</span>
                        {stageStatus.visual === "running" && <span className="stage-status-badge running">streaming...</span>}
                        {stageStatus.visual === "done" && <span className="stage-status-badge done">✓ done</span>}
                        {stageStatus.visual === "failed" && <span className="stage-status-badge" style={{color: "#fca5a5", background: "rgba(239,68,68,0.1)"}}>❌ failed</span>}
                    </div>
                    {stageOutputs.visual && <div className={`stream-output ${stageStatus.visual === "running" ? "active" : ""}`}>{stageOutputs.visual}{stageStatus.visual === "running" && <span className="typing-cursor" />}</div>}
                </div>
                {visualPrompt && (
                  <div className="visual-result">
                    <h3 style={{color: 'var(--text-1)', marginBottom: '12px'}}>Generated Visual Prompt</h3>
                    <div className="visual-prompt-box" style={{background: 'var(--surface-active)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-active)'}}>
                       {visualPrompt}
                    </div>
                    {/* Optional Image Rendering would go here */}
                  </div>
                )}
             </div>
          </div>
        )}
      </main>
    </div>
  );
}
"""

with open("app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
