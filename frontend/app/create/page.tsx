'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function CreateProduction() {
  const router = useRouter();
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('');
  const [outcome, setOutcome] = useState('');
  const [style, setStyle] = useState('educational');
  const [channel, setChannel] = useState('linkedin');

  const [ideas, setIdeas] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateIdeas = async () => {
    setIsGenerating(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/ideas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, style, target_language: 'es' })
      });
      if (res.ok) {
        const data = await res.json();
        setIdeas(data.ideas);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const startRun = (idea: string) => {
    const params = new URLSearchParams({
      idea,
      topic,
      style,
      target_language: 'es',
      image_prompt_language: 'en'
    });
    router.push(`/runs/new?${params.toString()}`);
  };

  return (
    <div className="create-page" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '8px' }}>Start a production</h1>
      <p style={{ color: 'var(--text-2)', marginBottom: '32px' }}>Turn an intent into a controlled multi-agent workflow.</p>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '32px' }}>
        {/* Left Column: Brief */}
        <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '4px' }}>Production brief</h2>
          <p style={{ color: 'var(--text-3)', fontSize: '13px', marginBottom: '24px' }}>Define the outcome before assigning work to agents.</p>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-2)', marginBottom: '8px' }}>Topic / working title</label>
            <input 
              type="text" 
              className="ui-input" 
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="e.g. Why AI agents fail in production" 
              style={{ width: '100%', padding: '12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text-1)' }}
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-2)', marginBottom: '8px' }}>Audience</label>
            <input 
              type="text" 
              className="ui-input" 
              value={audience}
              onChange={e => setAudience(e.target.value)}
              placeholder="CTOs, engineering leaders, founders" 
              style={{ width: '100%', padding: '12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text-1)' }}
            />
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-2)', marginBottom: '8px' }}>Desired outcome</label>
            <input 
              type="text" 
              className="ui-input" 
              value={outcome}
              onChange={e => setOutcome(e.target.value)}
              placeholder="Educate and generate qualified conversations" 
              style={{ width: '100%', padding: '12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text-1)' }}
            />
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-2)', marginBottom: '8px' }}>Content style</label>
            <div style={{ display: 'flex', gap: '12px' }}>
              {['educational', 'story', 'opinion'].map(s => (
                <button 
                  key={s}
                  onClick={() => setStyle(s)}
                  style={{ 
                    flex: 1, padding: '12px', borderRadius: '8px', textTransform: 'capitalize',
                    background: style === s ? 'rgba(124, 58, 237, 0.15)' : 'var(--bg-2)',
                    border: `1px solid ${style === s ? 'var(--accent)' : 'var(--border)'}`,
                    color: style === s ? 'var(--text-0)' : 'var(--text-2)'
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: '32px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-2)', marginBottom: '8px' }}>Output channels</label>
            <div style={{ display: 'flex', gap: '12px' }}>
              {['linkedin', 'article', 'carousel', 'x'].map(c => (
                <button 
                  key={c}
                  onClick={() => setChannel(c)}
                  style={{ 
                    padding: '8px 16px', borderRadius: '20px', textTransform: 'capitalize', fontSize: '13px',
                    background: channel === c ? 'rgba(124, 58, 237, 0.15)' : 'var(--bg-2)',
                    border: '1px solid transparent',
                    color: channel === c ? 'var(--text-0)' : 'var(--text-3)'
                  }}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button 
              onClick={handleGenerateIdeas}
              disabled={isGenerating || !topic.trim()}
              style={{ 
                background: 'var(--accent)', color: '#fff', padding: '12px 24px', borderRadius: '8px', 
                fontWeight: 600, border: 'none', cursor: 'pointer', opacity: (isGenerating || !topic.trim()) ? 0.5 : 1
              }}
            >
              {isGenerating ? 'Generating ideas...' : 'Generate ideas →'}
            </button>
          </div>
        </div>

        {/* Right Column: Agent Plan & Ideas */}
        <div>
          <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '24px' }}>Agent plan</h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {['Idea strategist', 'Research agent', 'Writer', 'Editor', 'Visual agent'].map((agent, i) => (
                <div key={agent} style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--bg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 12px var(--accent)' }}></div>
                  </div>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-1)' }}>{agent}</div>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '32px', padding: '16px', borderRadius: '8px', background: 'var(--bg-2)', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-3)', marginBottom: '4px' }}>Model policy</div>
              <div style={{ fontSize: '13px', color: 'var(--text-1)', marginBottom: '8px' }}>Balanced quality · fallback enabled</div>
              <span style={{ fontSize: '11px', color: 'var(--success)', background: 'var(--success-dim)', padding: '2px 8px', borderRadius: '12px' }}>Commercial safe</span>
            </div>
          </div>

          {/* Ideas Results */}
          {ideas.length > 0 && (
            <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '16px' }}>Generated Ideas</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {ideas.map((idea, i) => (
                  <div 
                    key={i} 
                    onClick={() => startRun(idea)}
                    style={{ padding: '12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: '8px', cursor: 'pointer', fontSize: '13px' }}
                    className="sidebar-link"
                  >
                    <div style={{ color: 'var(--text-2)', fontSize: '11px', marginBottom: '4px' }}>Idea {i+1}</div>
                    {idea}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
