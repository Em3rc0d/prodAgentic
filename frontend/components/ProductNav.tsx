"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const items: { href: string; label: string; icon: ReactNode }[] = [
  { href: "/", label: "Create", icon: <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18M3 12h18" /></svg> },
  { href: "/library", label: "Library", icon: <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h10a2 2 0 0 1 2 2V20H7a2 2 0 0 1-2-2V4.5Z" /><path d="M7 4.5V18a2 2 0 0 0 2 2" /><path d="M17 7h2a1 1 0 0 1 1 1v10a2 2 0 0 1-2 2h-1" /></svg> },
  { href: "/review", label: "Review", icon: <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h14v15H5z" /><path d="m8 12 2.3 2.3L16 8.8" /></svg> },
  { href: "/profiles", label: "Profiles", icon: <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.2" /><path d="M5.5 20c.6-4 2.8-6 6.5-6s5.9 2 6.5 6" /></svg> },
  { href: "/publishing", label: "Publish", icon: <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12.5 20 5l-6.5 14-2.7-5.8L4 12.5Z" /><path d="m10.8 13.2 3.7-3.6" /></svg> },
  { href: "/scheduling", label: "Schedule", icon: <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14" rx="2" /><path d="M8 3.5v4M16 3.5v4M4 9.5h16" /><path d="M9 14h2M13 14h2" /></svg> },
];

export function ProductNav() {
  const pathname = usePathname();

  return (
    <nav className="product-rail" aria-label="Primary product navigation">
      <Link href="/" className="product-rail__brand" aria-label="prodAgentic home">
        <span className="product-rail__mark">pA</span>
        <span className="product-rail__brand-copy"><strong>prodAgentic</strong><small>Content OS</small></span>
      </Link>

      <div className="product-rail__items">
        {items.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`product-rail__item${active ? " product-rail__item--active" : ""}`}
              aria-current={active ? "page" : undefined}
              title={item.label}
            >
              <span className="product-rail__icon">{item.icon}</span>
              <span className="product-rail__label">{item.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="product-rail__footer">
        <span className="product-rail__pulse" />
        <span>System ready</span>
      </div>
    </nav>
  );
}