"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { fetchProfilesV2, type ProfileV2 } from "@/lib/api";
import { fetchRuntimeReadiness, type RuntimeReadiness } from "@/lib/r2";
import styles from "./r2-app-shell.module.css";

export const R2_NAVIGATION = [
  ["/home", "Home", "01"],
  ["/profiles", "Profiles", "02"],
  ["/create", "Create", "03"],
  ["/review", "Review", "04"],
  ["/calendar", "Calendar", "05"],
  ["/analytics", "Analytics", "06"],
] as const;

const UNKNOWN: RuntimeReadiness = {
  state: "UNREACHABLE",
  label: "Checking runtime",
  detail: "Readiness has not been observed yet.",
};

export function R2AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [profile, setProfile] = useState<ProfileV2 | null>(null);
  const [runtime, setRuntime] = useState<RuntimeReadiness>(UNKNOWN);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([fetchProfilesV2(), fetchRuntimeReadiness()]).then(([profilesResult, runtimeResult]) => {
      if (cancelled) return;
      if (profilesResult.status === "fulfilled") setProfile(profilesResult.value.profiles[0] ?? null);
      if (runtimeResult.status === "fulfilled") setRuntime(runtimeResult.value);
    });
    return () => { cancelled = true; };
  }, [pathname]);

  return (
    <div className={styles.shell} data-generation="mk1-r2">
      <aside className={styles.rail}>
        <Link href="/home" prefetch={false} className={styles.brand} aria-label="prodAgentic home">
          <span className={styles.mark}>pA</span>
          <span className={styles.brandCopy}><strong>prodAgentic</strong><small>Precision Telemetry</small></span>
        </Link>

        <div className={styles.profile} aria-label="Active Profile">
          <span className={styles.micro}>Active profile</span>
          <strong>{profile?.name || "No Profile yet"}</strong>
          <small>{profile ? `Profile v${profile.current_version}` : "Create one to start"}</small>
        </div>

        <nav className={styles.navigation} aria-label="Primary product navigation">
          {R2_NAVIGATION.map(([href, label, index]) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link key={href} href={href} prefetch={false} aria-current={active ? "page" : undefined} className={active ? styles.active : undefined}>
                <span className={styles.index} aria-hidden="true">{index}</span>
                <span className={styles.navLabel}>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className={styles.runtime} data-state={runtime.state} title={runtime.detail}>
          <span className={styles.runtimeDot} aria-hidden="true" />
          <span><strong>{runtime.label}</strong><small>{runtime.state === "READY" ? "Observed now" : "Open Home for detail"}</small></span>
        </div>
      </aside>
      <div className={styles.content} data-scroll-region="main">{children}</div>
    </div>
  );
}
