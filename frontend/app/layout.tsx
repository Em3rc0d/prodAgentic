import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "prodAgentic Engine",
  description:
    "Generate viral LinkedIn posts automatically using 5 specialized AI agents.",
};

import Sidebar from "@/components/Sidebar";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
