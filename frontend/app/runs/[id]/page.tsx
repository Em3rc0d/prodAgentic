'use client';

import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import SemanticOrb from '@/components/SemanticOrb';
import { createPipelineStream } from '@/lib/api';

type StageStatus = 'pending' | 'running' | 'done' | 'failed';
type StageKey = 'research' | 'write' | 'edit' | 'visual';

export default function RunPage({ params }: { params: { id: string } }) {
  const searchParams = useSearchParams();
  const idea = searchParams.get('idea');
  const topic = searchParams.get('topic');
  const style = searchParams.get('style');
  const targetLanguage = searchParams.get('target_language');
  
  const [pipelineState, setPipelineState] = useState<'starting' | 'running' | 'review' | 'done'>('starting');
  const [stageStatus, setStageStatus] = useState<Record<StageKey, StageStatus>>({
    research: 'pending', write: 'pending', edit: 'pending', visual: 'pending'
  });
  const [stageOutputs, setStageOutputs] = useState<Record<StageKey, string>>({
    research: '', write: '', edit: '', visual: ''
  });
  const [finalPost, setFinalPost] = useState('');
  const [hasUnsupportedClaims, setHasUnsupportedClaims] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // For chunks tracking
  const activeAttemptByStage = useRef<Record<StageKey, string | null>>({ research: null, write: null, edit: null, visual: null });
  const lastSequenceByAttempt = useRef<Record<string, number>>({});

  useEffect(() => {
    if (params.id === 'new' && idea && topic && style) {
      setPipelineState('running');
      if (esRef.current) esRef.current.close();
      const es = createPipelineStream(idea, topic, style, targetLanguage || 'en', 'en');
      esRef.current = es;

      es.onmessage = (e: MessageEvent) => {
        try {
          const msg = JSON.parse(e.data);
          
          if (msg.stage === "stage_start" || msg.stage === "stage.attempt_started") {
            const sKey = msg.stage_name as StageKey;
            setStageStatus(prev => ({ ...prev, [sKey]: "running" }));
            if (msg.attempt_id) {
                activeAttemptByStage.current[sKey] = msg.attempt_id;
                lastSequenceByAttempt.current[msg.attempt_id] = 0;
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
            setStageOutputs(prev => ({ ...prev, [sKey]: prev[sKey] + msg.text }));
          } else if (msg.stage === "stage_done" || msg.stage === "stage.completed") {
            setStageStatus(prev => ({ ...prev, [msg.stage_name as StageKey]: "done" }));
          } else if (msg.stage === "stage_failed" || msg.stage === "stage.failed") {
            const rawStage = msg.stage_name;
            if (rawStage && rawStage !== "unknown") {
                setStageStatus(prev => ({ ...prev, [rawStage as StageKey]: "failed" }));
                activeAttemptByStage.current[rawStage as StageKey] = null;
            }
          } else if (msg.stage === "pipeline.text_completed") {
            setFinalPost(msg.final_post || "");
            if (msg.unsupported_claims) setHasUnsupportedClaims(true);
            setPipelineState('review');
          } else if (msg.stage === "visual.prompt_started") {
            setStageStatus(prev => ({ ...prev, visual: "running" }));
          } else if (msg.stage === "visual.prompt_completed") {
            setStageStatus(prev => ({ ...prev, visual: "done" }));
          } else if (msg.stage === "visual.prompt_failed") {
            setStageStatus(prev => ({ ...prev, visual: "failed" }));
          } else if (msg.stage === "complete") {
            setFinalPost(msg.final_post || finalPost);
            setPipelineState('done');
            if (msg.post_id) {
               // Update URL to the real Mongo ID without reloading
               window.history.replaceState(null, '', `/runs/${msg.post_id}`);
            }
            es.close();
          } else if (msg.stage === "error") {
            es.close();
          } else if (msg.stage === "end") {
            es.close();
          }
        } catch (err) {}
      };
      
      return () => {
        if (esRef.current) esRef.current.close();
      };
    }
  }, [params.id, idea, topic, style, targetLanguage]);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 380px', gap: '32px' }}>
      <div className="run-main">
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '32px' }}>
          Live Agent Run
        </h1>

        <div className="agent-timeline" style={{ background: 'var(--bg-1)', borderRadius: '16px', padding: '32px', border: '1px solid var(--border)' }}>
          {['research', 'write', 'edit', 'visual'].map((stage, idx) => {
            const sKey = stage as StageKey;
            const status = stageStatus[sKey];
            const displayStatus = status === 'pending' ? 'waiting' : status;
            return (
              <div key={sKey} style={{ display: 'flex', gap: '20px', marginBottom: idx < 3 ? '48px' : 0, position: 'relative' }}>
                {idx < 3 && <div style={{ position: 'absolute', top: '32px', left: '16px', bottom: '-48px', width: '2px', background: 'var(--border)' }}></div>}
                
                <SemanticOrb status={displayStatus as any} size="md" />
                
                <div style={{ flex: 1 }}>
                  <h3 style={{ textTransform: 'capitalize', color: status === 'running' ? 'var(--accent-light)' : 'var(--text-0)', marginBottom: '8px' }}>{sKey} Agent</h3>
                  {status === 'running' && <span style={{ color: 'var(--accent-light)', fontSize: '13px' }}>Working...</span>}
                  
                  {stageOutputs[sKey] && (
                    <div style={{ marginTop: '16px', padding: '16px', background: 'var(--bg-2)', borderRadius: '8px', border: '1px solid var(--border)', maxHeight: '200px', overflowY: 'auto', fontSize: '13px', color: 'var(--text-2)', fontFamily: 'monospace' }}>
                      {stageOutputs[sKey]}
                      {status === 'running' && <span style={{ display: 'inline-block', width: '6px', height: '14px', background: 'var(--accent-light)', marginLeft: '4px', animation: 'blink 1s infinite' }}></span>}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="run-sidebar">
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '16px' }}>
          Review & Approve
        </h2>
        
        {pipelineState === 'review' || pipelineState === 'done' ? (
          <div style={{ background: 'var(--bg-1)', borderRadius: '16px', padding: '24px', border: '1px solid var(--border)' }}>
            
            {hasUnsupportedClaims && (
              <div style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', padding: '12px', borderRadius: '8px', border: '1px solid rgba(245,158,11,0.2)', marginBottom: '16px', fontSize: '13px' }}>
                <strong style={{ display: 'block', marginBottom: '4px' }}>⚠️ NEEDS REVIEW</strong>
                Unsupported claims detected. Human verification required.
              </div>
            )}

            <div style={{ background: '#fff', borderRadius: '8px', padding: '16px', color: '#000', fontSize: '14px', whiteSpace: 'pre-wrap', marginBottom: '24px' }}>
              {finalPost}
            </div>

            <button style={{ width: '100%', padding: '12px', background: 'var(--accent)', color: '#fff', borderRadius: '8px', fontWeight: 600, border: 'none' }}>
              Approve for Publication
            </button>
          </div>
        ) : (
          <div style={{ background: 'var(--bg-1)', borderRadius: '16px', padding: '24px', border: '1px solid var(--border)', color: 'var(--text-3)', textAlign: 'center' }}>
            Waiting for text compilation...
          </div>
        )}
      </div>
    </div>
  );
}
