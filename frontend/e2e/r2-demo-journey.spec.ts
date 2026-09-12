import { expect, test } from "@playwright/test";
import fs from "node:fs";

const WEB = process.env.R2_WEB_URL || "http://127.0.0.1:3000";
const API = process.env.R2_API_URL || "http://127.0.0.1:8000";
const STATE_FILE = process.env.R2_STATE_FILE || "r2-journey-state.json";

const setup = {
  name: "R2 Demo Profile",
  account_type: "education",
  goals: ["educate", "build_authority"],
  audience: "software engineers validating governed content systems",
  voice: ["technical", "direct"],
  batch_size: 4,
  channels: ["manual_export"],
  examples: [
    {
      kind: "caption",
      label: "R2 demo example",
      text: "A reliable content system preserves authority across planning, rendering, QA and review. #reliability",
    },
  ],
};

test("R2 demo produces a real carousel, reaches Review, approves and exports", async ({ page }) => {
  test.setTimeout(120_000);

  const ready = await page.request.get(`${API}/health/ready`);
  expect(ready.ok()).toBeTruthy();
  expect((await ready.json()).status).toBe("READY_DEMO");

  const proposalResponse = await page.request.post(`${API}/api/profiles/inference-proposals`, { data: setup });
  expect(proposalResponse.ok()).toBeTruthy();
  const proposal = await proposalResponse.json();
  const acceptanceResponse = await page.request.post(`${API}/api/profiles`, {
    data: { setup, proposal_digest: proposal.proposal_digest },
  });
  expect(acceptanceResponse.ok()).toBeTruthy();
  const accepted = await acceptanceResponse.json();
  expect(accepted.profile.current_version).toBe(1);

  await page.goto(`${WEB}/create`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Create for R2 Demo Profile" })).toBeVisible();
  await page.getByRole("button", { name: "1" }).click();
  await page.getByRole("button", { name: "Add optional constraints" }).click();
  await page.getByLabel("Format").selectOption("carousel");

  await page.getByRole("button", { name: "Generate next batch" }).click();
  await expect(page).toHaveURL(/\/review$/, { timeout: 90_000 });
  await expect(page.getByRole("heading", { name: "Review", exact: true })).toBeVisible();
  const exactLink = page.getByRole("link", { name: /Open exact revision/ }).first();
  await expect(exactLink).toBeVisible();
  await exactLink.click();

  await expect(page.getByTestId("s5-review-preview")).toHaveAttribute("data-qa-readiness", "READY_FOR_REVIEW", { timeout: 30_000 });
  await expect(page.getByTestId("s5-review-preview")).toHaveAttribute("data-s7-approval", "AVAILABLE");
  expect(await page.getByRole("button", { name: /Show rendered page/ }).count()).toBeGreaterThanOrEqual(2);
  await expect(page.getByText(/Page 1 of 3/)).toBeVisible();

  const revisionId = new URL(page.url()).pathname.split("/").filter(Boolean).at(-1);
  expect(revisionId).toBeTruthy();

  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByTestId("s7-approved-receipt")).toBeVisible();
  await expect(page.getByTestId("s5-review-preview")).toHaveAttribute("data-s7-approval", "APPROVED");

  const exportResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "GET" && response.url().includes("/manual-export"),
  );
  await page.getByRole("button", { name: "Download manual package" }).click();
  const exportResponse = await exportResponsePromise;
  expect(exportResponse.ok()).toBeTruthy();
  expect(exportResponse.headers()["content-type"]).toContain("application/zip");

  fs.writeFileSync(STATE_FILE, JSON.stringify({ revisionId }, null, 2));
  await page.screenshot({ path: "r2-demo-approved.png", fullPage: true });
});

test("R2 approved carousel survives backend restart with owned pages intact", async ({ page }) => {
  test.setTimeout(60_000);
  const state = JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as { revisionId: string };

  const ready = await page.request.get(`${API}/health/ready`);
  expect(ready.ok()).toBeTruthy();
  expect((await ready.json()).status).toBe("READY_DEMO");

  await page.goto(`${WEB}/review/${encodeURIComponent(state.revisionId)}`, { waitUntil: "domcontentloaded" });
  const root = page.getByTestId("s5-review-preview");
  await expect(root).toHaveAttribute("data-qa-readiness", "READY_FOR_REVIEW");
  await expect(root).toHaveAttribute("data-s7-approval", "APPROVED");
  await expect(page.getByText("Approved · package frozen", { exact: true })).toBeVisible();
  expect(await page.getByRole("button", { name: /Show rendered page/ }).count()).toBeGreaterThanOrEqual(2);
  await expect(page.getByText(/Page 1 of 3/)).toBeVisible();
  await page.screenshot({ path: "r2-demo-after-restart.png", fullPage: true });
});
