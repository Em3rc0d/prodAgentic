import React from 'react';

type OrbStatus = 'working' | 'done' | 'waiting' | 'failed';

interface SemanticOrbProps {
  status: OrbStatus;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function SemanticOrb({ status, size = 'md', className = '' }: SemanticOrbProps) {
  return (
    <div className={`orb-container ${size} ${className}`}>
      <div className={`orb-core ${status}`}>
        {/* The inner glow */}
        {status === 'working' && <div className="orb-pulse" />}
        {status === 'done' && <div className="orb-stable-glow" />}
        {status === 'waiting' && <div className="orb-dim" />}
        {status === 'failed' && <div className="orb-halo-error" />}
      </div>
    </div>
  );
}
