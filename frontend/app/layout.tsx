import type { Metadata } from "next";
import { AuthGate } from "@/components/AuthGate";
import { R2AppShell } from "@/components/r2/R2AppShell";
import "./globals.css";
import "./mk1-tokens.css";
import "./r2-system.css";

export const metadata: Metadata = {
  title: "prodAgentic",
  description: "Controlled agentic content production for professional identities.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthGate><R2AppShell>{children}</R2AppShell></AuthGate>
      </body>
    </html>
  );
}
