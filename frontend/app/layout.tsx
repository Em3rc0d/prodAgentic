import type { Metadata } from "next";
import { AuthGate } from "@/components/AuthGate";
import { ProductNav } from "@/components/ProductNav";
import { Mk1AppShell } from "@/components/mk1/Mk1AppShell";
import { mk1ShellEnabled } from "@/lib/mk1-feature-flags";
import "./globals.css";
import "./mk1-tokens.css";
import "./product-shell.css";
import "./premium-workspace.css";
import "./premium-responsive.css";
import "./premium-create.css";

export const metadata: Metadata = {
  title: "prodAgentic",
  description: "Controlled agentic content production for professional identities.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthGate>
          {mk1ShellEnabled ? <Mk1AppShell>{children}</Mk1AppShell> : <>{children}<ProductNav /></>}
        </AuthGate>
      </body>
    </html>
  );
}
