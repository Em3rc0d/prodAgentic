"use client";

import { ThinkingOrb, OrbState } from "thinking-orbs";
import React, { useEffect, useState } from "react";

export type StageKey = "idea" | "research" | "write" | "edit" | "visual";

const STAGE_TO_ORB_STATE: Record<StageKey, OrbState> = {
  idea: "shaping",
  research: "searching",
  write: "composing",
  edit: "solving",
  visual: "working",
};

const STAGE_LABELS: Record<StageKey, string> = {
  idea: "Generating ideas",
  research: "Researching topic",
  write: "Writing content",
  edit: "Editing content",
  visual: "Generating visuals",
};

interface AgentActivityIndicatorProps {
  stage: StageKey;
  status: "pending" | "running" | "done" | "failed";
  size?: 20 | 64;
}

export function AgentActivityIndicator({
  stage,
  status,
  size = 20,
}: AgentActivityIndicatorProps) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    // eslint-disable-next-line
    setReducedMotion(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  if (status === "pending" || status === "done" || status === "failed") {
    return null;
  }

  const orbState = STAGE_TO_ORB_STATE[stage];
  const label = STAGE_LABELS[stage];

  if (reducedMotion) {
    return (
      <div 
        className="inline-flex items-center justify-center text-xs font-semibold text-accent-light"
        aria-label={label}
        role="status"
      >
        [ Working... ]
      </div>
    );
  }

  return (
    <div 
      className="inline-flex items-center justify-center" 
      aria-label={label}
      role="status"
      title={label}
    >
      <ThinkingOrb state={orbState} size={size} />
    </div>
  );
}
