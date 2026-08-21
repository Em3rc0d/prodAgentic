import type { Metadata } from "next";
import Link from "next/link";
import { AuthGate } from "@/components/AuthGate";
import "./globals.css";

export const metadata: Metadata = {
  title: "prodAgentic Engine",
  description: "Controlled agentic content production for professional identities.",
};

const navLink = { color: "var(--text-1)", textDecoration: "none", padding: "8px 10px", borderRadius: 7, fontSize: 13 } as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthGate>
          {children}
          <nav aria-label="Primary product navigation" style={{ position: "fixed", right: 18, bottom: 18, zIndex: 1000, display: "flex", gap: 8, padding: 6, borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)", boxShadow: "0 10px 30px rgba(0,0,0,.2)" }}>
            <Link href="/" style={navLink}>Create</Link><Link href="/library" style={navLink}>Library</Link><Link href="/profiles" style={navLink}>Profiles</Link><Link href="/publishing" style={navLink}>Publish</Link><Link href="/scheduling" style={{ ...navLink, background: "var(--surface-active)" }}>Schedule</Link>
          </nav>
        </AuthGate>
      </body>
    </html>
  );
}
