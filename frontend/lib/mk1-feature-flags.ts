export const mk1ShellEnabled = process.env.NEXT_PUBLIC_MK1_SHELL === "true";
export const mk1ProfileV2Enabled =
  mk1ShellEnabled && process.env.NEXT_PUBLIC_MK1_PROFILE_V2 === "true";
export const mk1BatchPlanningEnabled =
  mk1ShellEnabled && process.env.NEXT_PUBLIC_MK1_BATCH_PLANNING === "true";
export const mk1PublishingEnabled =
  mk1ShellEnabled && process.env.NEXT_PUBLIC_MK1_PUBLISHING === "true";
export const mk1AnalyticsEnabled =
  mk1ShellEnabled && process.env.NEXT_PUBLIC_MK1_ANALYTICS === "true";
