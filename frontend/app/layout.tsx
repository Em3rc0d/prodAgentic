import type { Metadata } from "next";
import { AuthGate } from "@/components/AuthGate";
import { ProductNav } from "@/components/ProductNav";
import "./globals.css";
import "./product-shell.css";
import "./premium-workspace.css";
import "./premium-responsive.css";

export const metadata: Metadata = {
  title: "prodAgentic",
  description: "Controlled agentic content production for professional identities.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthGate>
          {children}
          <ProductNav />
        </AuthGate>
      </body>
    </html>
  );
}
