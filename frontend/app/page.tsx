'use client';

import Link from 'next/link';

export default function CommandCenter() {
  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '8px' }}>Command Center</h1>
          <p style={{ color: 'var(--text-2)' }}>Overview of your agentic production environment.</p>
        </div>
        <Link href="/create" style={{ background: 'var(--accent)', color: '#fff', padding: '10px 20px', borderRadius: '8px', fontWeight: 500, textDecoration: 'none' }}>
          + New Production
        </Link>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px', marginBottom: '48px' }}>
        <div style={{ background: 'var(--bg-1)', padding: '24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <div style={{ color: 'var(--text-3)', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Throughput (30d)</div>
          <div style={{ fontSize: '32px', fontWeight: 600, color: 'var(--text-0)' }}>1,432</div>
          <div style={{ color: 'var(--success)', fontSize: '13px', marginTop: '8px' }}>↑ 12% vs last month</div>
        </div>
        
        <div style={{ background: 'var(--bg-1)', padding: '24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <div style={{ color: 'var(--text-3)', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Human Approval Rate</div>
          <div style={{ fontSize: '32px', fontWeight: 600, color: 'var(--text-0)' }}>94.2%</div>
          <div style={{ color: 'var(--success)', fontSize: '13px', marginTop: '8px' }}>↑ 2.1% vs last month</div>
        </div>

        <div style={{ background: 'var(--bg-1)', padding: '24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <div style={{ color: 'var(--text-3)', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Avg Time to Publish</div>
          <div style={{ fontSize: '32px', fontWeight: 600, color: 'var(--text-0)' }}>2m 14s</div>
          <div style={{ color: 'var(--text-2)', fontSize: '13px', marginTop: '8px' }}>Stable</div>
        </div>
      </div>

      <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-0)', marginBottom: '20px' }}>Recent Runs</h2>
      
      <div style={{ background: 'var(--bg-1)', borderRadius: '16px', border: '1px solid var(--border)', overflow: 'hidden' }}>
        {/* Placeholder for recent runs */}
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-3)' }}>
          <div style={{ fontSize: '24px', marginBottom: '16px' }}>🏃</div>
          <p>No recent runs found. Start a new production to see it here.</p>
        </div>
      </div>
    </div>
  );
}
