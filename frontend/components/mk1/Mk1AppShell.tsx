"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import styles from "./mk1-app-shell.module.css";

const navigation = [
  ["/home", "Home"],
  ["/profiles", "Profiles"],
  ["/create", "Create"],
  ["/review", "Review"],
  ["/calendar", "Calendar"],
  ["/analytics", "Analytics"],
] as const;

export function Mk1AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className={styles.shell} data-generation="mk1">
      <aside className={styles.rail}>
        <Link href="/home" className={styles.brand} aria-label="prodAgentic home">
          <span className={styles.mark}>pA</span>
          <span><strong>prodAgentic</strong><small>Content OS</small></span>
        </Link>
        <div className={styles.profile} aria-label="Active Profile">
          <small>Profile</small>
          <span>Current identity</span>
        </div>
        <nav className={styles.navigation} aria-label="Primary product navigation">
          {navigation.map(([href, label]) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link key={href} href={href} aria-current={active ? "page" : undefined} className={active ? styles.active : undefined}>
                <span className={styles.statusMarker} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className={styles.health}><span aria-hidden="true" />System ready</div>
      </aside>
      <div className={styles.content}>{children}</div>
    </div>
  );
}
