export const mk1ShellEnabled = process.env.NEXT_PUBLIC_MK1_SHELL === "true";
export const mk1ProfileV2Enabled =
  mk1ShellEnabled && process.env.NEXT_PUBLIC_MK1_PROFILE_V2 === "true";
