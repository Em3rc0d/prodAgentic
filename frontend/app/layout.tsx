import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "prodAgentic Engine",
  description:
    "Generate viral LinkedIn posts automatically using 5 specialized AI agents.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
        <nav
          aria-label="Primary product navigation"
          style={{
            position: "fixed",
            right: 18,
            bottom: 18,
            zIndex: 1000,
            display: "flex",
            gap: 8,
            padding: 6,
            borderRadius: 10,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            boxShadow: "0 10px 30px rgba(0,0,0,.2)",
          }}
        >
          <Link
            href="/"
            style={{
              color: "var(--text-1)",
              textDecoration: "none",
              padding: "8px 10px",
              borderRadius: 7,
              fontSize: 13,
            }}
          >
            Create
          </Link>
          <Link
            href="/library"
            style={{
              color: "var(--text-1)",
              textDecoration: "none",
              padding: "8px 10px",
              borderRadius: 7,
              background: "var(--surface-active)",
              fontSize: 13,
            }}
          >
            Library
          </Link>
        </nav>
      </body>
    </html>
  );
}
