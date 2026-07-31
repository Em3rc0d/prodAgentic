"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { fetchIdeas, createPipelineStream, renderVisual } from "@/lib/api";
import { AgentActivityIndicator } from "@/components/AgentActivityIndicator";

type Style = "educational" | "storytelling" | "controversial";
type StageKey = "research" | "write" | "edit" | "visual";
type AppMode = "idle" | "loading_ideas" | "ideas_ready" | "pipeline_running" | "text_ready" | "pipeline_done";
type StageStatus = "pending" | "running" | "done" | "failed";
type TabId = "brief" | "ideas" | "research" | "draft" | "final" | "visual" | "diagnostics";

const PIPELINE_STAGES: { key: StageKey; label: string; emoji: string; tab: TabId }[] = [
  { key: "research", label: "Research Agent", emoji: "🔎", tab: "research" },
  { key: "write", label: "Content Writer", emoji: "✍️", tab: "draft" },
  { key: "edit", label: "Editor Agent", emoji: "🧪", tab: "final" },
  { key: "visual", label: "Visual Agent", emoji: "🎨", tab: "visual" },
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
  
  const [renderedImageUrl, setRenderedImageUrl] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<"IDLE" | "QUEUED" | "RENDERING" | "READY" | "FAILED" | "CANCELLED">("IDLE");

  // Stable rendering states
  const [pipelineRunId, setPipelineRunId] = useState<string | null>(null);
  const [selectedRatio, setSelectedRatio] = useState<string>("16:9");
  const [selectedStyle, setSelectedStyle] = useState<string>("");
  const [renderIntentId, setRenderIntentId] = useState<string>("");
  const [lastParams, setLastParams] = useState<{ prompt: string; ratio: string; style: string } | null>(null);

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
  
  // Diagnostics event history
  const [eventHistory, setEventHistory] = useState<Record<string, unknown>[]>([]);

  const esRef = useRef<EventSource | null>(null);
  const activeAttemptByStage = useRef<Record<StageKey, string | null>>({
    research: null, write: null, edit: null, visual: null,
  });
  const lastSequenceByAttempt = useRef<Record<string, number>>({});

  useEffect(() => {
    return () => { if (esRef.current) esRef.current.close(); };
  }, []);

  const resetPipeline = useCallback(() => {
    setStageStatus({ research: "pending", write: "pending", edit: "pending", visual: "pending" });
    setStageOutputs({ research: "", write: "", edit: "", visual: "" });
    setStageModels({ research: null, write: null, edit: null, visual: null });
    setCurrentStage(null); setFinalPost(""); setVisualPrompt("");
    setEventHistory([]);
    activeAttemptByStage.current = { research: null, write: null, edit: null, visual: null };
    lastSequenceByAttempt.current = {};
    setRenderedImageUrl(null);
    setRenderStatus("IDLE");
    setPipelineRunId(null);
    setRenderIntentId("");
    setLastParams(null);
  }, []);

  const handleGenerateIdeas = useCallback(async () => {
    if (!topic.trim()) return;
    setError(null); setMode("loading_ideas"); setIdeas([]); setSelectedIdea(null);
    setFinalPost(""); setVisualPrompt(""); resetPipeline();
    setActiveTab("brief");

    try {
      const result = await fetchIdeas(topic.trim(), style, targetLanguage);
      setIdeas(result);
      setMode("ideas_ready");
      setActiveTab("ideas");
    } catch (e) {
      setError("Failed to generate ideas. Is the backend running on :8000?");
      setMode("idle");
    }
  }, [topic, style, targetLanguage]);

  const handleSelectIdea = useCallback((idea: string) => {
    if (mode === "pipeline_running") return;
    setSelectedIdea(idea); setMode("pipeline_running"); resetPipeline();
    setActiveTab("research");

    if (esRef.current) esRef.current.close();
    const es = createPipelineStream(idea, topic, style, targetLanguage, imagePromptLanguage);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      try {
        const msg = JSON.parse(e.data);
        
        setEventHistory((prev) => [...prev, { ...msg, _ts: new Date().toISOString() }]);

        if (msg.run_id) {
          setPipelineRunId(msg.run_id);
        }

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
          // Auto switch tab if it makes sense
          const sKey = msg.stage_name as StageKey;
          if (sKey === "research") setActiveTab("draft");
        } else if (msg.stage === "stage_failed" || msg.stage === "stage.failed") {
          const rawStage = msg.stage_name;
          if (rawStage && rawStage !== "unknown") {
              setStageStatus((prev) => ({ ...prev, [rawStage as StageKey]: "failed" }));
              activeAttemptByStage.current[rawStage as StageKey] = null;
          }
          setCurrentStage(null); setMode("ideas_ready"); setFinalPost("");
        } else if (msg.stage === "pipeline.text_completed") {
          setFinalPost(msg.final_post || "");
          setMode("text_ready"); 
          setActiveTab("final");
        } else if (msg.stage === "visual.prompt_started") {
          setCurrentStage("visual");
          setStageStatus((prev) => ({ ...prev, visual: "running" }));
        } else if (msg.stage === "visual.prompt_completed") {
          setVisualPrompt(msg.content || "");
          setStageStatus((prev) => ({ ...prev, visual: "done" }));
          setCurrentStage(null);
        } else if (msg.stage === "visual.prompt_failed") {
          setStageStatus((prev) => ({ ...prev, visual: "failed" }));
          setCurrentStage(null);
        } else if (msg.stage === "complete") {
          setFinalPost(msg.final_post || finalPost);
          if (msg.visual_prompt) setVisualPrompt(msg.visual_prompt);
          setMode("pipeline_done"); setCurrentStage(null); es.close();
        } else if (msg.stage === "error") {
          setError(msg.reason || "Pipeline encountered a terminal error");
          setMode("ideas_ready"); setFinalPost(""); setActiveTab("brief"); setSelectedIdea(null); es.close();
        } else if (msg.stage === "end") {
          es.close();
        }
      } catch (err) {}
    };
    es.onerror = () => {
      setError("Pipeline stream interrupted. Check backend logs."); setMode("ideas_ready"); setActiveTab("brief"); setSelectedIdea(null); es.close();
    };
  }, [topic, style, mode, targetLanguage, imagePromptLanguage, finalPost, resetPipeline]);

  function handleReset() {
    if (esRef.current) esRef.current.close();
    setMode("idle"); setIdeas([]); setSelectedIdea(null); setError(null); setFinalPost("");
    setActiveTab("brief"); resetPipeline();
  }

  function handleCopy() {
    navigator.clipboard.writeText(finalPost).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
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
        
        <div className="global-pipeline-summary" style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            {mode === "pipeline_running" && currentStage ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--surface-active)', padding: '4px 12px', borderRadius: '16px', fontSize: '13px' }}>
                    <AgentActivityIndicator stage={currentStage} status="running" size={20} />
                    <span>Pipeline: {currentStage.charAt(0).toUpperCase() + currentStage.slice(1)} {stageModels[currentStage] && <span style={{ color: 'var(--text-3)' }}>({stageModels[currentStage]})</span>}</span>
                </div>
            ) : mode === "text_ready" ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(59,130,246,0.1)', color: '#3b82f6', padding: '4px 12px', borderRadius: '16px', fontSize: '13px' }}>
                    <span>📝 Text Ready</span>
                </div>
            ) : mode === "pipeline_done" ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(34,197,94,0.1)', color: 'var(--success)', padding: '4px 12px', borderRadius: '16px', fontSize: '13px' }}>
                    <span>✅ Pipeline Complete</span>
                </div>
            ) : mode === "loading_ideas" ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--surface-active)', padding: '4px 12px', borderRadius: '16px', fontSize: '13px' }}>
                    <AgentActivityIndicator stage="idea" status="running" size={20} />
                    <span>Pipeline: Generating Ideas</span>
                </div>
            ) : null}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {mode !== "idle" && <button className="history-tab-btn" onClick={handleReset} style={{ marginLeft: 4 }}>↩ Reset</button>}
        </div>
      </header>
      
      <div className="workspace-tabs-bar" style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--surface)', padding: '0 16px' }}>
        {[
            { id: "brief", icon: "📝", label: "Brief" },
            { id: "ideas", icon: "💡", label: "Ideas", disabled: mode === "idle" || ideas.length === 0 },
            { id: "research", icon: "🔎", label: "Research", disabled: !selectedIdea },
            { id: "draft", icon: "✍️", label: "Draft", disabled: !selectedIdea },
            { id: "final", icon: "✨", label: "Final", disabled: !selectedIdea },
            { id: "visual", icon: "🎨", label: "Visual", disabled: !selectedIdea },
            { id: "diagnostics", icon: "⚙️", label: "Diagnostics", disabled: !selectedIdea }
        ].map((t) => (
            <button 
                key={t.id} 
                className={`tab-btn ${activeTab === t.id ? "active" : ""}`} 
                onClick={() => setActiveTab(t.id as TabId)}
                disabled={t.disabled}
                style={{ opacity: t.disabled ? 0.5 : 1, padding: '12px 16px', borderBottom: activeTab === t.id ? '2px solid var(--primary)' : '2px solid transparent', background: 'none', color: activeTab === t.id ? 'var(--text-1)' : 'var(--text-2)', cursor: t.disabled ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
                <span>{t.icon}</span> {t.label}
            </button>
        ))}
      </div>

      {error && (
        <div className="global-error-banner">⚠️ {error}</div>
      )}

      <main className="tab-content-area" style={{ padding: '24px' }}>
        {activeTab === "brief" && (
            <div className="brief-sidebar" style={{ maxWidth: '600px', margin: '0 auto' }}>
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
                  <option value="auto">Auto-detect</option>
                  <option value="en">English</option><option value="es">Español</option><option value="pt">Português</option>
                </select>
              </div>
              <div className="input-group">
                  <p className="sidebar-section-label">Image Prompt Language</p>
                  <select value={imagePromptLanguage} onChange={(e) => setImagePromptLanguage(e.target.value)} disabled={isRunning} className="language-select">
                    <option value="en">English</option><option value="es">Español</option><option value="pt">Português</option>
                  </select>
                </div>
              <button id="generate-btn" className="btn-generate" onClick={handleGenerateIdeas} disabled={!topic.trim() || isRunning}>
                {mode === "loading_ideas" ? "⏳ Generating..." : "⚡ Generate Ideas"}
              </button>
            </div>
        )}
        
        {activeTab === "ideas" && (
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
              {mode === "loading_ideas" && (
                <div className="ideas-section">
                  <div className="ideas-header"><span className="ideas-title">Generating ideas...</span><AgentActivityIndicator stage="idea" status="running" size={20} /></div>
                  <div className="ideas-grid">{[...Array(6)].map((_, i) => (<div key={i} className="skeleton" style={{ height: 72, animationDelay: `${i * 0.1}s` }} />))}</div>
                </div>
              )}
              {(mode === "ideas_ready" || mode === "pipeline_running" || mode === "text_ready" || mode === "pipeline_done") && ideas.length > 0 && (
                <div className="ideas-section">
                  <div className="ideas-header">
                    <span className="ideas-title">{mode === "ideas_ready" ? "Select an idea to start the pipeline" : "Idea selected"}</span>
                    <span className="ideas-count">{ideas.length} ideas</span>
                  </div>
                  <div className="ideas-grid">
                    {ideas.map((idea, i) => (
                      <button key={i} className={`idea-card ${selectedIdea === idea ? "selected" : ""}`} onClick={() => handleSelectIdea(idea)} disabled={mode === "pipeline_running" || mode === "text_ready" || mode === "pipeline_done"}>
                        <div className="idea-number">#{String(i + 1).padStart(2, "0")}</div>{idea}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
        )}

        {activeTab === "research" && (
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
                <div className={`stream-stage-header ${stageStatus.research === "running" ? "active" : stageStatus.research === "done" ? "done" : stageStatus.research === "failed" ? "failed" : ""}`}>
                    <span className="stage-emoji">🔎</span><span className="stage-label">Research Agent</span>
                    {stageStatus.research === "running" && <span className="stage-status-badge running">streaming...</span>}
                    {stageStatus.research === "done" && <span className="stage-status-badge done">✓ done</span>}
                    {stageStatus.research === "failed" && <span className="stage-status-badge" style={{color: "#fca5a5", background: "rgba(239,68,68,0.1)"}}>❌ failed</span>}
                    {stageModels.research && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-3)" }}>· {stageModels.research}</span>}
                </div>
                <div className={`stream-output ${stageStatus.research === "running" ? "active" : ""}`} style={{ minHeight: '300px' }}>{stageOutputs.research}{stageStatus.research === "running" && <span className="typing-cursor" />}</div>
            </div>
        )}

        {activeTab === "draft" && (
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
                <div className={`stream-stage-header ${stageStatus.write === "running" ? "active" : stageStatus.write === "done" ? "done" : stageStatus.write === "failed" ? "failed" : ""}`}>
                    <span className="stage-emoji">✍️</span><span className="stage-label">Content Writer</span>
                    {stageStatus.write === "running" && <span className="stage-status-badge running">streaming...</span>}
                    {stageStatus.write === "done" && <span className="stage-status-badge done">✓ done</span>}
                    {stageStatus.write === "failed" && <span className="stage-status-badge" style={{color: "#fca5a5", background: "rgba(239,68,68,0.1)"}}>❌ failed</span>}
                    {stageModels.write && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-3)" }}>· {stageModels.write}</span>}
                </div>
                <div className={`stream-output ${stageStatus.write === "running" ? "active" : ""}`} style={{ minHeight: '300px' }}>{stageOutputs.write}{stageStatus.write === "running" && <span className="typing-cursor" />}</div>
            </div>
        )}

        {activeTab === "final" && (
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
                <div className={`stream-stage-header ${stageStatus.edit === "running" ? "active" : stageStatus.edit === "done" ? "done" : stageStatus.edit === "failed" ? "failed" : ""}`}>
                    <span className="stage-emoji">🧪</span><span className="stage-label">Editor Agent</span>
                    {stageStatus.edit === "running" && <span className="stage-status-badge running">streaming...</span>}
                    {stageStatus.edit === "done" && <span className="stage-status-badge done">✓ done</span>}
                    {stageStatus.edit === "failed" && <span className="stage-status-badge" style={{color: "#fca5a5", background: "rgba(239,68,68,0.1)"}}>❌ failed</span>}
                    {stageModels.edit && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-3)" }}>· {stageModels.edit}</span>}
                </div>
                <div className={`stream-output ${stageStatus.edit === "running" ? "active" : ""}`} style={{ marginBottom: '24px' }}>{stageOutputs.edit}{stageStatus.edit === "running" && <span className="typing-cursor" />}</div>
                
                {finalPost && (
                    <div className="content-preview" style={{ marginTop: '32px' }}>
                        <div className="preview-header"><span className="preview-header-title">🔗 LinkedIn Preview</span>{wordCount > 0 && <span className="word-count">{wordCount}w</span>}</div>
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
                    </div>
                )}
            </div>
        )}

        {activeTab === "visual" && (
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
                <div className="stream-section">
                    <div className={`stream-stage-header ${stageStatus.visual === "running" ? "active" : stageStatus.visual === "done" ? "done" : stageStatus.visual === "failed" ? "failed" : ""}`}>
                        <span className="stage-emoji">🎨</span><span className="stage-label">Visual Agent</span>
                        {stageStatus.visual === "running" && <span className="stage-status-badge running">streaming...</span>}
                        {stageStatus.visual === "done" && <span className="stage-status-badge done">✓ done</span>}
                        {stageStatus.visual === "failed" && <span className="stage-status-badge" style={{color: "#fca5a5", background: "rgba(239,68,68,0.1)"}}>❌ failed</span>}
                        {stageModels.visual && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-3)" }}>· {stageModels.visual}</span>}
                    </div>
                    {stageOutputs.visual && <div className={`stream-output ${stageStatus.visual === "running" ? "active" : ""}`}>{stageOutputs.visual}{stageStatus.visual === "running" && <span className="typing-cursor" />}</div>}
                </div>
                {visualPrompt && (
                  <div className="visual-result" style={{ marginTop: '24px' }}>
                    <h3 style={{color: 'var(--text-1)', marginBottom: '12px'}}>Generated Visual Prompt</h3>
                    <textarea 
                      className="visual-prompt-box" 
                      style={{background: 'var(--surface-active)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-active)', marginBottom: '16px', width: '100%', minHeight: '100px', color: 'var(--text-1)', fontFamily: 'inherit', resize: 'vertical'}}
                      value={visualPrompt}
                      onChange={(e) => setVisualPrompt(e.target.value)}
                    />
                    
                    {/* Approved Aspect Ratio and Style Selectors */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                      <div>
                        <label htmlFor="aspect-ratio-select" style={{ display: 'block', color: 'var(--text-2)', fontSize: '13px', marginBottom: '6px' }}>Aspect Ratio</label>
                        <select 
                          id="aspect-ratio-select"
                          value={selectedRatio} 
                          onChange={(e) => setSelectedRatio(e.target.value)} 
                          style={{ width: '100%', padding: '8px', borderRadius: '4px', background: 'var(--surface)', color: 'var(--text-1)', border: '1px solid var(--border)' }}
                        >
                          <option value="16:9">16:9 (Landscape)</option>
                          <option value="1:1">1:1 (Square)</option>
                          <option value="4:5">4:5 (Portrait)</option>
                        </select>
                      </div>
                      <div>
                        <label htmlFor="visual-style-select" style={{ display: 'block', color: 'var(--text-2)', fontSize: '13px', marginBottom: '6px' }}>Visual Style</label>
                        <select 
                          id="visual-style-select"
                          value={selectedStyle} 
                          onChange={(e) => setSelectedStyle(e.target.value)} 
                          style={{ width: '100%', padding: '8px', borderRadius: '4px', background: 'var(--surface)', color: 'var(--text-1)', border: '1px solid var(--border)' }}
                        >
                          <option value="">Default (None)</option>
                          <option value="technical_editorial">Technical Editorial</option>
                          <option value="cinematic">Cinematic</option>
                          <option value="minimal">Minimal</option>
                          <option value="illustration">Illustration</option>
                          <option value="photorealistic">Photorealistic</option>
                        </select>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                      <button 
                        className="btn-generate"
                        style={{ padding: '8px 16px', borderRadius: '4px', background: 'var(--primary)', color: 'white', border: 'none', cursor: 'pointer' }}
                        onClick={async () => {
                          setRenderStatus("RENDERING");
                          try {
                            const currentParams = { prompt: visualPrompt, ratio: selectedRatio, style: selectedStyle };
                            let intentId = renderIntentId;
                            if (!lastParams || lastParams.prompt !== currentParams.prompt || lastParams.ratio !== currentParams.ratio || lastParams.style !== currentParams.style) {
                              intentId = `intent-${Date.now()}-${Math.random().toString(36).slice(2)}`;
                              setRenderIntentId(intentId);
                              setLastParams(currentParams);
                            }
                            
                            const actualRunId = pipelineRunId || `run-fallback-${Date.now()}`;
                            const idempotencyKey = `${actualRunId}-${intentId}`;

                            const result = await renderVisual(
                              visualPrompt, 
                              selectedRatio, 
                              selectedStyle, 
                              actualRunId, 
                              idempotencyKey
                            );
                            
                            switch (result.status) {
                              case "QUEUED":
                                setRenderStatus("QUEUED");
                                break;
                              case "RENDERING":
                                setRenderStatus("RENDERING");
                                break;
                              case "READY":
                                setRenderedImageUrl(result.asset_url ?? result.url ?? null);
                                setRenderStatus("READY");
                                break;
                              case "FAILED":
                                setRenderStatus("FAILED");
                                break;
                              case "CANCELLED":
                                setRenderStatus("CANCELLED");
                                break;
                              default:
                                setRenderStatus("FAILED");
                            }
                          } catch (err) {
                            console.error("Failed to render image", err);
                            setRenderStatus("FAILED");
                          }
                        }}
                        disabled={renderStatus === "RENDERING" || renderStatus === "QUEUED"}
                      >
                        {renderStatus === "RENDERING" || renderStatus === "QUEUED" ? "Rendering..." : "Generar imagen"}
                      </button>
                      <button 
                        style={{ padding: '8px 16px', borderRadius: '4px', background: 'var(--surface)', color: 'var(--text-1)', border: '1px solid var(--border)', cursor: 'pointer' }}
                        onClick={() => navigator.clipboard.writeText(visualPrompt)}
                      >
                        Copiar prompt
                      </button>
                      {renderStatus !== "IDLE" && (
                        <span style={{ marginLeft: '8px', fontSize: '13px', color: renderStatus === "FAILED" ? '#fca5a5' : renderStatus === "READY" ? 'var(--success)' : 'var(--text-2)' }}>
                          Status: {renderStatus}
                        </span>
                      )}
                    </div>
                    
                    {["RENDERING", "READY", "FAILED", "QUEUED", "CANCELLED"].includes(renderStatus) ? (
                      <div className="image-render-preview" style={{ borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)', background: 'var(--surface)' }}>
                        {renderStatus === "RENDERING" || renderStatus === "QUEUED" ? (
                          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-3)' }}>
                            <AgentActivityIndicator stage="visual" status="running" size={20} />
                            <div style={{ marginTop: '12px' }}>{renderStatus === "QUEUED" ? "Queued..." : "Generating image..."}</div>
                          </div>
                        ) : renderStatus === "READY" && renderedImageUrl ? (
                          /* eslint-disable-next-line @next/next/no-img-element */
                          <img 
                            src={renderedImageUrl} 
                            alt={visualPrompt}
                            style={{ width: '100%', display: 'block', aspectRatio: selectedRatio.replace(':', '/'), objectFit: 'cover' }}
                          />
                        ) : renderStatus === "CANCELLED" ? (
                          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-3)' }}>
                            Rendering cancelled.
                          </div>
                        ) : (
                          <div style={{ padding: '40px', textAlign: 'center', color: '#fca5a5' }}>
                            Failed to generate image.
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                )}
            </div>
        )}

        {activeTab === "diagnostics" && (
            <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
                <h2 style={{ color: 'var(--text-1)', marginBottom: '16px' }}>Pipeline Diagnostics</h2>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
                    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '16px' }}>
                        <h3 style={{ color: 'var(--text-2)', fontSize: '12px', textTransform: 'uppercase', marginBottom: '12px' }}>Model Routing</h3>
                        {PIPELINE_STAGES.map(s => (
                            <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-active)' }}>
                                <span style={{ color: 'var(--text-1)' }}>{s.label}</span>
                                <span style={{ color: stageModels[s.key] ? 'var(--primary)' : 'var(--text-3)', fontFamily: 'monospace' }}>
                                    {stageModels[s.key] || 'Pending'}
                                </span>
                            </div>
                        ))}
                    </div>
                    
                    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '16px' }}>
                        <h3 style={{ color: 'var(--text-2)', fontSize: '12px', textTransform: 'uppercase', marginBottom: '12px' }}>Status Tracker</h3>
                        {PIPELINE_STAGES.map(s => (
                            <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-active)' }}>
                                <span style={{ color: 'var(--text-1)' }}>{s.label}</span>
                                <span style={{ 
                                    color: stageStatus[s.key] === 'done' ? 'var(--success)' : 
                                           stageStatus[s.key] === 'failed' ? '#fca5a5' :
                                           stageStatus[s.key] === 'running' ? 'var(--primary)' : 'var(--text-3)' 
                                }}>
                                    {stageStatus[s.key].toUpperCase()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                <div style={{ background: '#1e1e1e', borderRadius: '8px', overflow: 'hidden' }}>
                    <div style={{ background: '#252526', padding: '8px 16px', borderBottom: '1px solid #333', color: '#ccc', fontSize: '12px', display: 'flex', justifyContent: 'space-between' }}>
                        <span>SSE Event History</span>
                        <span>{eventHistory.length} events</span>
                    </div>
                    <div style={{ padding: '16px', fontFamily: 'monospace', fontSize: '12px', color: '#d4d4d4' }}>
                        {eventHistory.length === 0 ? (
                            <div style={{ color: '#666', fontStyle: 'italic' }}>No events recorded yet.</div>
                        ) : (
                            eventHistory.map((evt, i) => (
                                <div key={i} style={{ marginBottom: '8px', borderBottom: '1px solid #333', paddingBottom: '8px' }}>
                                    <div style={{ color: '#569cd6', marginBottom: '4px' }}>[{new Date(evt._ts as string).toLocaleTimeString()}] {(evt.stage as string) || 'unknown'}</div>
                                    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', paddingLeft: '16px', color: '#ce9178' }}>
                                        {JSON.stringify(evt, (k, v) => k === '_ts' || k === 'stage' ? undefined : v, 2)}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        )}

      </main>
    </div>
  );
}
