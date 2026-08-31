"use client";
/* eslint-disable @next/next/no-img-element */

import { useState, useRef, useCallback, useEffect } from "react";
import { fetchIdeas, createPipelineStream, renderVisual } from "@/lib/api";
import { AgentActivityIndicator } from "@/components/AgentActivityIndicator";
import { PremiumScene } from "@/components/PremiumScene";
import styles from "./create-studio.module.css";

type Style = "educational" | "storytelling" | "controversial";
type StageKey = "research" | "write" | "edit" | "visual";
type AppMode = "idle" | "loading_ideas" | "ideas_ready" | "pipeline_running" | "text_ready" | "pipeline_done";
type StageStatus = "pending" | "running" | "done" | "failed";
type TabId = "brief" | "ideas" | "research" | "draft" | "final" | "visual" | "diagnostics";

const PIPELINE_STAGES: { key: StageKey; label: string; tab: TabId }[] = [
  { key: "research", label: "Research pass", tab: "research" },
  { key: "write", label: "Writing pass", tab: "draft" },
  { key: "edit", label: "Editorial pass", tab: "final" },
  { key: "visual", label: "Visual pass", tab: "visual" },
];

const TABS: { id: TabId; label: string }[] = [
  { id: "brief", label: "Brief" },
  { id: "ideas", label: "Ideas" },
  { id: "research", label: "Research" },
  { id: "draft", label: "Draft" },
  { id: "final", label: "Final" },
  { id: "visual", label: "Visual" },
  { id: "diagnostics", label: "Diagnostics" },
];

const STYLE_OPTIONS: { value: Style; label: string; desc: string }[] = [
  { value: "educational", label: "Educational", desc: "Teach with clarity" },
  { value: "storytelling", label: "Storytelling", desc: "Build a narrative" },
  { value: "controversial", label: "Controversial", desc: "Take a strong position" },
];

const TOPIC_PRESETS = ["Spring Boot", "Kafka", "MongoDB", "Telecom", "AI aplicado", "Microservices", "System Design"];

function Glyph({ name }: { name: TabId | StageKey | "spark" | "copy" | "reset" | "linkedin" }) {
  const common = { viewBox: "0 0 24 24", "aria-hidden": true } as const;
  if (name === "brief") return <svg {...common}><path d="M6 3.8h8.4L18 7.4V20H6z"/><path d="M14 3.8v4h4M9 12h6M9 15.5h5"/></svg>;
  if (name === "ideas" || name === "spark") return <svg {...common}><path d="M9.4 15.8h5.2M10 19h4"/><path d="M8.2 13.2A6 6 0 1 1 15.8 13.2c-.9.7-1.3 1.4-1.3 2.6h-5c0-1.2-.4-1.9-1.3-2.6Z"/><path d="M12 2V.8M5.1 5.1 4.2 4.2M18.9 5.1l.9-.9"/></svg>;
  if (name === "research") return <svg {...common}><circle cx="10.8" cy="10.8" r="5.8"/><path d="m15.2 15.2 4.6 4.6M8.5 10.8h4.6M10.8 8.5v4.6"/></svg>;
  if (name === "draft" || name === "write") return <svg {...common}><path d="m5 19 3.2-.7L18.7 7.8a2.2 2.2 0 0 0-3.1-3.1L5.1 15.2 5 19Z"/><path d="m14.5 5.8 3.1 3.1"/></svg>;
  if (name === "final" || name === "edit") return <svg {...common}><path d="m7 12.5 3 3 7-7"/><path d="M12 2.8 14.2 6l3.8.5-2.7 2.7.6 3.8-3.9-1.9L8.1 13l.6-3.8L6 6.5 9.8 6 12 2.8Z" opacity=".45"/></svg>;
  if (name === "visual") return <svg {...common}><rect x="3.5" y="4" width="17" height="16" rx="2.5"/><circle cx="9" cy="9.5" r="1.6"/><path d="m5.7 17 4.2-4.4 3.2 3 2.4-2.4 2.8 3.8"/></svg>;
  if (name === "diagnostics") return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M12 2.8v2M12 19.2v2M21.2 12h-2M4.8 12h-2M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4M18.5 18.5l-1.4-1.4M6.9 6.9 5.5 5.5"/></svg>;
  if (name === "copy") return <svg {...common}><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1"/></svg>;
  if (name === "reset") return <svg {...common}><path d="M4.5 8.5V4.5h4"/><path d="M5.2 7.2A8 8 0 1 1 4 14"/></svg>;
  if (name === "linkedin") return <svg {...common}><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 10v7M8 7.2v.1M12 17v-4.1c0-1.8 3.8-2.3 3.8.2V17M12 10v7"/></svg>;
  return null;
}

function statusLabel(status: StageStatus) {
  if (status === "done") return "Complete";
  if (status === "running") return "Working";
  if (status === "failed") return "Failed";
  return "Waiting";
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>("brief");
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState<Style>("educational");
  const [targetLanguage, setTargetLanguage] = useState<string>("es");
  const [imagePromptLanguage, setImagePromptLanguage] = useState<string>("en");
  const [mode, setMode] = useState<AppMode>("idle");
  const [ideas, setIdeas] = useState<string[]>([]);
  const [selectedIdea, setSelectedIdea] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renderedImageUrl, setRenderedImageUrl] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<"IDLE" | "QUEUED" | "RENDERING" | "READY" | "FAILED" | "CANCELLED">("IDLE");
  const [pipelineRunId, setPipelineRunId] = useState<string | null>(null);
  const [selectedRatio, setSelectedRatio] = useState<string>("4:5");
  const [selectedStyle, setSelectedStyle] = useState<string>("technical_editorial");
  const [renderIntentId, setRenderIntentId] = useState<string>("");
  const [lastParams, setLastParams] = useState<{ prompt: string; ratio: string; style: string } | null>(null);
  const [stageStatus, setStageStatus] = useState<Record<StageKey, StageStatus>>({ research: "pending", write: "pending", edit: "pending", visual: "pending" });
  const [stageOutputs, setStageOutputs] = useState<Record<StageKey, string>>({ research: "", write: "", edit: "", visual: "" });
  const [stageModels, setStageModels] = useState<Record<StageKey, string | null>>({ research: null, write: null, edit: null, visual: null });
  const [currentStage, setCurrentStage] = useState<StageKey | null>(null);
  const [finalPost, setFinalPost] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [copied, setCopied] = useState(false);
  const [eventHistory, setEventHistory] = useState<Record<string, unknown>[]>([]);

  const esRef = useRef<EventSource | null>(null);
  const activeAttemptByStage = useRef<Record<StageKey, string | null>>({ research: null, write: null, edit: null, visual: null });
  const lastSequenceByAttempt = useRef<Record<string, number>>({});

  useEffect(() => () => { if (esRef.current) esRef.current.close(); }, []);

  const resetPipeline = useCallback(() => {
    setStageStatus({ research: "pending", write: "pending", edit: "pending", visual: "pending" });
    setStageOutputs({ research: "", write: "", edit: "", visual: "" });
    setStageModels({ research: null, write: null, edit: null, visual: null });
    setCurrentStage(null); setFinalPost(""); setVisualPrompt(""); setEventHistory([]);
    activeAttemptByStage.current = { research: null, write: null, edit: null, visual: null };
    lastSequenceByAttempt.current = {};
    setRenderedImageUrl(null); setRenderStatus("IDLE"); setPipelineRunId(null); setRenderIntentId(""); setLastParams(null);
  }, []);

  const handleGenerateIdeas = useCallback(async () => {
    if (!topic.trim()) return;
    setError(null); setMode("loading_ideas"); setIdeas([]); setSelectedIdea(null); setFinalPost(""); setVisualPrompt(""); resetPipeline(); setActiveTab("brief");
    try {
      const result = await fetchIdeas(topic.trim(), style, targetLanguage);
      setIdeas(result); setMode("ideas_ready"); setActiveTab("ideas");
    } catch {
      setError("Failed to generate ideas. Is the backend running on :8000?"); setMode("idle");
    }
  }, [topic, style, targetLanguage, resetPipeline]);

  const handleSelectIdea = useCallback((idea: string) => {
    if (mode === "pipeline_running") return;
    setSelectedIdea(idea); setMode("pipeline_running"); resetPipeline(); setActiveTab("research");
    if (esRef.current) esRef.current.close();
    const es = createPipelineStream(idea, topic, style, targetLanguage, imagePromptLanguage);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      try {
        const msg = JSON.parse(e.data);
        setEventHistory((prev) => [...prev, { ...msg, _ts: new Date().toISOString() }]);
        if (msg.run_id) setPipelineRunId(msg.run_id);

        if (msg.stage === "stage_start" || msg.stage === "stage.attempt_started") {
          const sKey = msg.stage_name as StageKey;
          setCurrentStage(sKey); setStageStatus((prev) => ({ ...prev, [sKey]: "running" }));
          if (msg.attempt_id) { activeAttemptByStage.current[sKey] = msg.attempt_id; lastSequenceByAttempt.current[msg.attempt_id] = 0; }
          if (msg.selected_model) setStageModels((prev) => ({ ...prev, [sKey]: msg.selected_model }));
        } else if (msg.stage === "stage.attempt_reset") {
          const sKey = msg.stage_name as StageKey;
          activeAttemptByStage.current[sKey] = null; setStageOutputs((prev) => ({ ...prev, [sKey]: "" }));
        } else if (msg.stage === "chunk" || msg.stage === "stage.chunk") {
          const sKey = msg.stage_name as StageKey;
          const attemptId = msg.attempt_id;
          const seq = msg.event_sequence || 0;
          if (attemptId && activeAttemptByStage.current[sKey] !== attemptId) return;
          if (attemptId && seq > 0) { if (seq <= (lastSequenceByAttempt.current[attemptId] || 0)) return; lastSequenceByAttempt.current[attemptId] = seq; }
          setStageOutputs((prev) => ({ ...prev, [sKey]: prev[sKey] + msg.text }));
        } else if (msg.stage === "stage_done" || msg.stage === "stage.completed") {
          setStageStatus((prev) => ({ ...prev, [msg.stage_name as StageKey]: "done" }));
          const sKey = msg.stage_name as StageKey;
          if (sKey === "research") setActiveTab("draft");
        } else if (msg.stage === "stage_failed" || msg.stage === "stage.failed") {
          const rawStage = msg.stage_name;
          if (rawStage && rawStage !== "unknown") { setStageStatus((prev) => ({ ...prev, [rawStage as StageKey]: "failed" })); activeAttemptByStage.current[rawStage as StageKey] = null; }
          setCurrentStage(null); setMode("ideas_ready"); setFinalPost("");
        } else if (msg.stage === "pipeline.text_completed") {
          setFinalPost(msg.final_post || ""); setMode("text_ready"); setActiveTab("final");
        } else if (msg.stage === "visual.prompt_started") {
          setCurrentStage("visual"); setStageStatus((prev) => ({ ...prev, visual: "running" }));
        } else if (msg.stage === "visual.prompt_completed") {
          setVisualPrompt(msg.content || ""); setStageStatus((prev) => ({ ...prev, visual: "done" })); setCurrentStage(null);
        } else if (msg.stage === "visual.prompt_failed") {
          setStageStatus((prev) => ({ ...prev, visual: "failed" })); setCurrentStage(null);
        } else if (msg.stage === "complete") {
          setFinalPost(msg.final_post || finalPost); if (msg.visual_prompt) setVisualPrompt(msg.visual_prompt); setMode("pipeline_done"); setCurrentStage(null); es.close();
        } else if (msg.stage === "error") {
          setError(msg.reason || "Pipeline encountered a terminal error"); setMode("ideas_ready"); setFinalPost(""); setActiveTab("brief"); setSelectedIdea(null); es.close();
        } else if (msg.stage === "end") es.close();
      } catch {
        // Ignore malformed stream frames; the connection-level handler reports terminal failures.
      }
    };
    es.onerror = () => { setError("Pipeline stream interrupted. Check backend logs."); setMode("ideas_ready"); setActiveTab("brief"); setSelectedIdea(null); es.close(); };
  }, [topic, style, mode, targetLanguage, imagePromptLanguage, finalPost, resetPipeline]);

  function handleReset() {
    if (esRef.current) esRef.current.close();
    setMode("idle"); setIdeas([]); setSelectedIdea(null); setError(null); setFinalPost(""); setActiveTab("brief"); resetPipeline();
  }

  function handleCopy() {
    navigator.clipboard.writeText(finalPost).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2500); });
  }

  async function handleRenderVisual() {
    setRenderStatus("RENDERING");
    try {
      const currentParams = { prompt: visualPrompt, ratio: selectedRatio, style: selectedStyle };
      let intentId = renderIntentId;
      if (!lastParams || lastParams.prompt !== currentParams.prompt || lastParams.ratio !== currentParams.ratio || lastParams.style !== currentParams.style) {
        intentId = `intent-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        setRenderIntentId(intentId); setLastParams(currentParams);
      }
      const actualRunId = pipelineRunId || `run-fallback-${Date.now()}`;
      const idempotencyKey = `${actualRunId}-${intentId}`;
      const result = await renderVisual(visualPrompt, selectedRatio, selectedStyle, actualRunId, idempotencyKey);
      switch (result.status) {
        case "QUEUED": setRenderStatus("QUEUED"); break;
        case "RENDERING": setRenderStatus("RENDERING"); break;
        case "READY": setRenderedImageUrl(result.asset_url ?? result.url ?? null); setRenderStatus("READY"); break;
        case "FAILED": setRenderStatus("FAILED"); break;
        case "CANCELLED": setRenderStatus("CANCELLED"); break;
        default: setRenderStatus("FAILED");
      }
    } catch (err) {
      console.error("Failed to render image", err); setRenderStatus("FAILED");
    }
  }

  const isRunning = mode === "pipeline_running" || mode === "loading_ideas";
  const wordCount = finalPost ? finalPost.trim().split(/\s+/).filter(Boolean).length : 0;
  const completedStages = PIPELINE_STAGES.filter((stage) => stageStatus[stage.key] === "done").length;
  const tabDisabled = (id: TabId) => id === "ideas" ? mode === "idle" || ideas.length === 0 : ["research", "draft", "final", "visual", "diagnostics"].includes(id) ? !selectedIdea : false;

  return (
    <main className={styles.page}>
      <section className={styles.studio}>
        <header className={styles.header}>
          <div className={styles.headerCopy}>
            <span className={styles.eyebrow}>Content studio</span>
            <div className={styles.titleRow}>
              <h1>Create content</h1>
              <span className={styles.beta}>AI orchestration</span>
            </div>
            <p>Turn one professional idea into a traceable, review-ready publication asset.</p>
          </div>
          <div className={styles.headerActions}>
            <div className={`${styles.runState} ${mode === "pipeline_running" ? styles.runStateLive : ""}`}>
              <span className={styles.runDot} />
              {mode === "pipeline_running" && currentStage ? `Pipeline · ${currentStage}` : mode === "loading_ideas" ? "Generating ideas" : mode === "text_ready" ? <span>📝 Text Ready</span> : mode === "pipeline_done" ? "Pipeline complete" : "Workspace ready"}
            </div>
            {mode !== "idle" && <button className={styles.ghostButton} onClick={handleReset}><Glyph name="reset" />Reset</button>}
          </div>
        </header>

        <nav className={styles.stageNav} aria-label="Content workflow stages">
          {TABS.map((tab) => {
            const disabled = tabDisabled(tab.id);
            const active = activeTab === tab.id;
            return (
              <button key={tab.id} className={`${styles.stageTab} ${active ? `${styles.stageTabActive} active` : ""}`} onClick={() => setActiveTab(tab.id)} disabled={disabled}>
                <Glyph name={tab.id} />{tab.label}
              </button>
            );
          })}
        </nav>

        {error && <div className={styles.errorBanner}><span>!</span>{error}</div>}

        <div className={styles.workspace}>
          <aside className={`${styles.panel} ${styles.briefPanel}`}>
            <div className={styles.panelHeading}>
              <div><span className={styles.panelEyebrow}>01 · Direction</span><h2>Creative brief</h2></div>
              <span className={styles.panelStatus}>{topic.trim() ? "Ready" : "Waiting"}</span>
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="topic-input">Topic</label>
              <input id="topic-input" className={styles.textInput} type="text" placeholder="e.g. Kafka, Spring Boot..." value={topic} onChange={(e) => setTopic(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleGenerateIdeas()} disabled={isRunning} />
              <div className={styles.presets}>
                {TOPIC_PRESETS.map((preset) => <button key={preset} className={`${styles.preset} ${topic === preset ? styles.presetActive : ""}`} onClick={() => setTopic(preset)} disabled={isRunning}>{preset}</button>)}
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>Style</label>
              <div className={styles.styleGrid}>
                {STYLE_OPTIONS.map((option) => (
                  <button key={option.value} className={`${styles.styleCard} ${style === option.value ? styles.styleCardActive : ""}`} onClick={() => setStyle(option.value)} disabled={isRunning}>
                    <span className={styles.styleIcon}><Glyph name={option.value === "educational" ? "ideas" : option.value === "storytelling" ? "draft" : "spark"} /></span>
                    <span><strong>{option.label}</strong><small>{option.desc}</small></span>
                    <span className={styles.radioMark} />
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.compactFields}>
              <div className={styles.formGroup}>
                <label htmlFor="target-language">Target language</label>
                <div className={styles.selectWrap}>
                  <select id="target-language" value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)} disabled={isRunning}>
                    <option value="auto">Auto-detect</option><option value="en">English</option><option value="es">Español</option><option value="pt">Português</option>
                  </select>
                </div>
              </div>
              <div className={styles.formGroup}>
                <label htmlFor="image-prompt-language">Image prompt</label>
                <div className={styles.selectWrap}>
                  <select id="image-prompt-language" value={imagePromptLanguage} onChange={(e) => setImagePromptLanguage(e.target.value)} disabled={isRunning}>
                    <option value="en">English</option><option value="es">Español</option><option value="pt">Português</option>
                  </select>
                </div>
              </div>
            </div>

            <button id="generate-btn" className={styles.primaryButton} onClick={handleGenerateIdeas} disabled={!topic.trim() || isRunning}>
              <Glyph name="spark" />{mode === "loading_ideas" ? "Generating..." : "Generate Ideas"}<span className={styles.buttonArrow}>→</span>
            </button>
          </aside>

          <section className={`${styles.panel} ${styles.canvasPanel}`}>
            {activeTab === "brief" && (
              <div className={styles.briefCanvas}>
                <div className={styles.sceneWrap}><PremiumScene variant="create" /></div>
                <div className={styles.canvasIntro}>
                  <span className={styles.canvasKicker}>Controlled generation</span>
                  <h2>One brief. Four specialized passes.</h2>
                  <p>Define the direction on the left. prodAgentic keeps research, writing, editing and visual work observable without exposing you to implementation noise.</p>
                </div>
                <div className={styles.pipelineStrip}>
                  {PIPELINE_STAGES.map((stage, index) => (
                    <div className={styles.pipelineMini} key={stage.key}>
                      <span className={styles.pipelineMiniIndex}>0{index + 1}</span>
                      <div><strong>{stage.label}</strong><small>{statusLabel(stageStatus[stage.key])}</small></div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "ideas" && (
              <div className={styles.canvasContent}>
                <div className={styles.sectionHeading}><div><span className={styles.panelEyebrow}>02 · Explore</span><h2>{mode === "loading_ideas" ? "Generating directions" : "Choose a content direction"}</h2></div>{ideas.length > 0 && <span className={styles.countBadge}>{ideas.length} ideas</span>}</div>
                {mode === "loading_ideas" ? <div className={styles.ideaGrid}>{[...Array(6)].map((_, i) => <div key={i} className={styles.ideaSkeleton} />)}</div> : (
                  <div className={styles.ideaGrid}>{ideas.map((idea, i) => <button key={i} className={`${styles.ideaCard} ${selectedIdea === idea ? styles.ideaCardActive : ""}`} onClick={() => handleSelectIdea(idea)} disabled={mode === "pipeline_running" || mode === "text_ready" || mode === "pipeline_done"}><span>0{i + 1}</span><strong>{idea}</strong><small>Select to start the controlled pipeline</small></button>)}</div>
                )}
              </div>
            )}

            {activeTab === "research" && <AgentStage title="Research Agent" stage="research" status={stageStatus.research} model={stageModels.research} output={stageOutputs.research} />}
            {activeTab === "draft" && <AgentStage title="Content Writer" stage="write" status={stageStatus.write} model={stageModels.write} output={stageOutputs.write} />}
            {activeTab === "final" && <AgentStage title="Editor Agent" stage="edit" status={stageStatus.edit} model={stageModels.edit} output={stageOutputs.edit} />}

            {activeTab === "visual" && (
              <div className={styles.canvasContent}>
                <div className={styles.sectionHeading}>
                  <div><span className={styles.panelEyebrow}>06 · Visual system</span><h2>Visual Agent</h2></div>
                  <StageBadge status={stageStatus.visual} />
                </div>
                {stageOutputs.visual && <div className={styles.streamBox}>{stageOutputs.visual}{stageStatus.visual === "running" && <span className={styles.cursor} />}</div>}
                {!visualPrompt && <div className={styles.emptyCanvas}><PremiumScene variant="create" compact /><h3>Visual direction will appear here</h3><p>The prompt remains editable before rendering. No asset is created until you ask for it.</p></div>}
                {visualPrompt && (
                  <div className={styles.visualWorkbench}>
                    <div className={styles.formGroup}><label htmlFor="visual-prompt">Generated visual prompt</label><textarea id="visual-prompt" className={styles.promptArea} value={visualPrompt} onChange={(e) => setVisualPrompt(e.target.value)} /></div>
                    <div className={styles.visualControls}>
                      <div className={styles.formGroup}><label htmlFor="aspect-ratio-select">Aspect Ratio</label><div className={styles.selectWrap}><select id="aspect-ratio-select" value={selectedRatio} onChange={(e) => setSelectedRatio(e.target.value)}><option value="16:9">16:9 · Landscape</option><option value="1:1">1:1 · Square</option><option value="4:5">4:5 · Portrait</option></select></div></div>
                      <div className={styles.formGroup}><label htmlFor="visual-style-select">Visual Style</label><div className={styles.selectWrap}><select id="visual-style-select" value={selectedStyle} onChange={(e) => setSelectedStyle(e.target.value)}><option value="">Default</option><option value="technical_editorial">Technical Editorial</option><option value="cinematic">Cinematic</option><option value="minimal">Minimal</option><option value="illustration">Illustration</option><option value="photorealistic">Photorealistic</option></select></div></div>
                    </div>
                    <div className={styles.visualActions}>
                      <button className={styles.primaryButtonSmall} onClick={handleRenderVisual} disabled={renderStatus === "RENDERING" || renderStatus === "QUEUED"}>{renderStatus === "RENDERING" || renderStatus === "QUEUED" ? "Rendering..." : "Generar imagen"}</button>
                      <button className={styles.secondaryButton} onClick={() => navigator.clipboard.writeText(visualPrompt)}><Glyph name="copy" />Copiar prompt</button>
                      {renderStatus !== "IDLE" && <span className={`${styles.renderStatus} ${renderStatus === "FAILED" ? styles.renderStatusFailed : renderStatus === "READY" ? styles.renderStatusReady : ""}`}>Status: {renderStatus}</span>}
                    </div>
                    {["RENDERING", "READY", "FAILED", "QUEUED", "CANCELLED"].includes(renderStatus) && (
                      <div className={styles.renderPreview}>
                        {renderStatus === "RENDERING" || renderStatus === "QUEUED" ? <div className={styles.renderPending}><AgentActivityIndicator stage="visual" status="running" size={22} /><span>{renderStatus === "QUEUED" ? "Queued..." : "Generating image..."}</span></div> : renderStatus === "READY" && renderedImageUrl ? <img src={renderedImageUrl} alt={visualPrompt} style={{ aspectRatio: selectedRatio.replace(":", "/") }} /> : renderStatus === "CANCELLED" ? <div className={styles.renderPending}>Rendering cancelled.</div> : <div className={`${styles.renderPending} ${styles.renderFailed}`}>Failed to generate image.</div>}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === "diagnostics" && (
              <div className={styles.canvasContent}>
                <div className={styles.sectionHeading}><div><span className={styles.panelEyebrow}>System evidence</span><h2>Pipeline Diagnostics</h2></div><span className={styles.countBadge}>{eventHistory.length} events</span></div>
                <div className={styles.diagnosticsGrid}>
                  <div className={styles.diagnosticCard}><h3>Model routing</h3>{PIPELINE_STAGES.map((stage) => <div className={styles.diagnosticRow} key={stage.key}><span>{stage.label}</span><code>{stageModels[stage.key] || "Pending"}</code></div>)}</div>
                  <div className={styles.diagnosticCard}><h3>Status tracker</h3>{PIPELINE_STAGES.map((stage) => <div className={styles.diagnosticRow} key={stage.key}><span>{stage.label}</span><strong data-status={stageStatus[stage.key]}>{stageStatus[stage.key].toUpperCase()}</strong></div>)}</div>
                </div>
                <div className={styles.eventLog}><div className={styles.eventLogHeader}><span>SSE event history</span><span>{eventHistory.length}</span></div><div className={styles.eventLogBody}>{eventHistory.length === 0 ? <p>No events recorded yet.</p> : eventHistory.map((evt, i) => <div className={styles.eventRow} key={i}><span>[{new Date(evt._ts as string).toLocaleTimeString()}] {(evt.stage as string) || "unknown"}</span><pre>{JSON.stringify(evt, (k, v) => k === "_ts" || k === "stage" ? undefined : v, 2)}</pre></div>)}</div></div>
              </div>
            )}
          </section>

          <aside className={`${styles.panel} ${styles.previewPanel}`}>
            <div className={styles.panelHeading}>
              <div><span className={styles.panelEyebrow}>Live artifact</span><h2>Preview</h2></div>
              <span className={styles.panelStatus}>{finalPost ? `${wordCount} words` : "Standby"}</span>
            </div>

            {finalPost ? (
              <div className={styles.linkedinPreview}>
                <div className={styles.linkedinTop}>
                  <div className={styles.linkedinAvatar}>E</div>
                  <div><strong>You</strong><span>Professional identity · now</span></div>
                  <span className={styles.linkedinMark}><Glyph name="linkedin" /></span>
                </div>
                <div className={styles.linkedinBody}>{finalPost}</div>
                {renderedImageUrl && <div className={styles.linkedinImage}><img src={renderedImageUrl} alt="Generated visual preview" /></div>}
                <div className={styles.linkedinMeta}><span>Review-ready asset</span><span>{selectedRatio}</span></div>
                <button className={styles.copyButton} onClick={handleCopy}><Glyph name="copy" />{copied ? "Copied!" : "Copy to clipboard"}</button>
              </div>
            ) : (
              <div className={styles.previewEmpty}>
                <div className={styles.previewScene}><PremiumScene variant="create" compact /></div>
                <h3>{selectedIdea ? "Pipeline in progress" : "Your final asset appears here"}</h3>
                <p>{selectedIdea ? "Watch the workflow canvas while prodAgentic builds the exact text and visual direction." : "Start with a focused brief. The preview remains quiet until there is something worth reviewing."}</p>
              </div>
            )}

            <div className={styles.progressCard}>
              <div className={styles.progressTop}><span>Workflow health</span><strong>{completedStages}/4</strong></div>
              <div className={styles.progressTrack}><span style={{ width: `${completedStages * 25}%` }} /></div>
              <div className={styles.progressList}>
                {PIPELINE_STAGES.map((stage) => <button key={stage.key} onClick={() => selectedIdea && setActiveTab(stage.tab)} disabled={!selectedIdea}><span data-status={stageStatus[stage.key]} /><div><strong>{stage.label}</strong><small>{stageModels[stage.key] || statusLabel(stageStatus[stage.key])}</small></div></button>)}
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function StageBadge({ status }: { status: StageStatus }) {
  return <span className={styles.stageBadge} data-status={status}><span />{statusLabel(status)}</span>;
}

function AgentStage({ title, stage, status, model, output }: { title: string; stage: StageKey; status: StageStatus; model: string | null; output: string }) {
  return (
    <div className={styles.canvasContent}>
      <div className={styles.sectionHeading}>
        <div><span className={styles.panelEyebrow}>Agent workspace</span><h2>{title}</h2></div>
        <StageBadge status={status} />
      </div>
      <div className={styles.agentMeta}><span className={styles.agentGlyph}><Glyph name={stage} /></span><div><strong>{status === "running" ? "Working on the selected direction" : status === "done" ? "Stage complete" : status === "failed" ? "Stage requires attention" : "Waiting for pipeline"}</strong><small>{model ? `Model · ${model}` : "Model routing will appear when the stage starts"}</small></div></div>
      <div className={`${styles.streamBox} ${status === "running" ? styles.streamBoxLive : ""}`}>{output || <span className={styles.streamPlaceholder}>Output will stream here in real time.</span>}{status === "running" && <span className={styles.cursor} />}</div>
    </div>
  );
}
