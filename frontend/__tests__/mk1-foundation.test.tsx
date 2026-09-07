import fs from "node:fs";
import path from "node:path";

import { render, screen } from "@testing-library/react";

import { Mk1AppShell } from "@/components/mk1/Mk1AppShell";

jest.mock("next/navigation", () => ({
  usePathname: () => "/review",
}));

describe("MK1 S0 application foundation", () => {
  it("exposes the frozen primary information architecture", () => {
    render(<Mk1AppShell><p>Review content</p></Mk1AppShell>);
    const navigation = screen.getByRole("navigation", { name: /primary product navigation/i });
    for (const label of ["Home", "Profiles", "Create", "Review", "Calendar", "Analytics"]) {
      expect(navigation).toHaveTextContent(label);
    }
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute("aria-current", "page");
  });

  it("contains the accepted Precision Telemetry token values", () => {
    const css = fs.readFileSync(path.join(process.cwd(), "app", "mk1-tokens.css"), "utf8");
    expect(css).toContain("--pa-canvas: #0b0d10");
    expect(css).toContain("--pa-signal: #d8ff45");
    expect(css).toContain("--pa-danger: #ff7070");
    expect(css).toContain("prefers-reduced-motion");
  });

  it("keeps long MK1 work surfaces reachable without requiring browser zoom", () => {
    const css = fs.readFileSync(
      path.join(process.cwd(), "components", "mk1", "mk1-app-shell.module.css"),
      "utf8",
    );
    const contentRule = css.match(/\.content\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(contentRule).toContain("height: 100dvh");
    expect(contentRule).toContain("overflow-y: auto");
    expect(contentRule).toContain("overflow-x: hidden");
    expect(contentRule).toContain("scrollbar-gutter: stable");
    expect(css).toContain("height: calc(100dvh - 68px)");
  });
});
