'use client';

export default function AnalyticsPage() {
  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ marginBottom: '40px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '8px' }}>Operations & Analytics</h1>
        <p style={{ color: 'var(--text-2)' }}>Monitor engine performance, costs, and model fallbacks.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '24px', marginBottom: '32px' }}>
        <div style={{ background: 'var(--bg-1)', borderRadius: '16px', padding: '24px', border: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '16px' }}>API Costs (30 Days)</h3>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '36px', fontWeight: 700, color: 'var(--text-0)' }}>$142.50</span>
            <span style={{ color: 'var(--text-2)', fontSize: '13px' }}>USD</span>
          </div>
          <div style={{ marginTop: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
              <span style={{ color: 'var(--text-2)' }}>Claude 3.5 Sonnet</span>
              <span style={{ color: 'var(--text-0)' }}>$85.20</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
              <span style={{ color: 'var(--text-2)' }}>Gemini 1.5 Pro</span>
              <span style={{ color: 'var(--text-0)' }}>$42.10</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
              <span style={{ color: 'var(--text-2)' }}>GPT-4o (Fallback)</span>
              <span style={{ color: 'var(--text-0)' }}>$15.20</span>
            </div>
          </div>
        </div>

        <div style={{ background: 'var(--bg-1)', borderRadius: '16px', padding: '24px', border: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '16px' }}>Model Reliability</h3>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ color: 'var(--text-2)', fontSize: '13px' }}>Primary Hit Rate</span>
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>98.5%</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ color: 'var(--text-2)', fontSize: '13px' }}>Fallback Triggers</span>
            <span style={{ color: 'var(--warning)', fontWeight: 600 }}>1.5%</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0' }}>
            <span style={{ color: 'var(--text-2)', fontSize: '13px' }}>Hard Failures</span>
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>0.0%</span>
          </div>
        </div>
      </div>

      <div style={{ background: 'var(--bg-1)', borderRadius: '16px', padding: '24px', border: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '16px' }}>Throughput over time</h3>
        <div style={{ height: '200px', display: 'flex', alignItems: 'flex-end', gap: '8px', paddingTop: '20px' }}>
          {[30, 45, 20, 60, 80, 50, 40, 90, 110, 85, 60, 75, 100, 120].map((h, i) => (
            <div key={i} style={{ flex: 1, background: 'var(--accent)', height: `${h}%`, borderRadius: '4px 4px 0 0', opacity: i === 13 ? 1 : 0.4 }} />
          ))}
        </div>
      </div>
    </div>
  );
}
