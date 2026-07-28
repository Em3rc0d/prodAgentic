import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Content Engine — LinkedIn Multi-Agent Pipeline",
  description:
    "Generate viral LinkedIn posts automatically using 5 specialized AI agents powered by Gemini 2.0 Flash.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
