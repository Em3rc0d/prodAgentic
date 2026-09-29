import { expect, test } from "@playwright/test";
import fs from "node:fs";

const WEB = process.env.R4_WEB_URL || "http://127.0.0.1:3000";
const API = process.env.R4_API_URL || "http://127.0.0.1:8000";
const STATE_FILE = process.env.R4_STATE_FILE || "r4-four-post-state.json";

const setup = {
  name: "R4 EM3RC0D Fixture",
  account_type: "education",
  goals: ["educate", "build_authority"],
  audience: "systems engineering students building practical technical skills",
  voice: ["technical", "direct"],
  batch_size: 4,
  channels: ["manual_export"],
  examples: [
    {
      kind: "caption",
      label: "Explicit topic authority fixture",
      text: "Aprende con ejemplos concretos de #SQL #Cloud #Networking #Architecture sin convertir cada publicación en el mismo tutorial.",
    },
  ],
};

type StoredRevision = { revisionId: string; pageCount: number };

async function visualPageCount(page: import("@playwright/test").Page) {
  const buttons = page.getByRole("button", { name: /Show rendered page/ });
  const count = await buttons.count();
  expect(count).toBeGreaterThan(0);
  await expect(page.getByText(new RegExp(`Page 1 of ${count}`))).toBeVisible();
  return count;
}

test("R4 creates exactly four visual-first posts and carries all four through Review", async ({ page }) => {
  test.setTimeout(240_000);

  const ready = await page.request.get(`${API}/health/ready`);
  expect(ready.ok()).toBeTruthy();
  expect((await ready.json()).status).toBe("READY_DEMO");

  const proposalResponse = await page.request.post(`${API}/api/profiles/inference-proposals`, { data: setup });
  expect(proposalResponse.ok()).toBeTruthy();
  const proposal = await proposalResponse.json();
  expect(new Set(proposal.topic_families).size).toBeGreaterThanOrEqual(4);

  const acceptanceResponse = await page.request.post(`${API}/api/profiles`, {
    data: { setup, proposal_digest: proposal.proposal_digest },
  });
  expect(acceptanceResponse.ok()).toBeTruthy();

  await page.goto(`${WEB}/create`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Create for R4 EM3RC0D Fixture" })).toBeVisible();
  await expect(page.getByRole("button", { name: "4", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Generate next batch" }).click();

  await expect(page).toHaveURL(/\/review$/, { timeout: 180_000 });
  await expect(page.getByRole("heading", { name: "Review", exact: true })).toBeVisible();

  const cards = page.getByTestId("r4-review-card");
  await expect(cards).toHaveCount(4, { timeout: 30_000 });

  const hrefs: string[] = [];
  const visibleTitles: string[] = [];
  for (let index = 0; index < 4; index += 1) {
    const card = cards.nth(index);
    const link = card.getByRole("link", { name: /Review exact creative/ });
    const href = await link.getAttribute("href");
    expect(href).toBeTruthy();
    hrefs.push(String(href));
    visibleTitles.push((await card.locator("h2").innerText()).trim());
  }
  expect(new Set(hrefs).size).toBe(4);
  expect(new Set(visibleTitles).size).toBe(4);

  const revisions: StoredRevision[] = [];
  for (const href of hrefs) {
    await page.goto(`${WEB}${href}`, { waitUntil: "domcontentloaded" });
    const root = page.getByTestId("s5-review-preview");
    await expect(root).toHaveAttribute("data-qa-readiness", "READY_FOR_REVIEW", { timeout: 30_000 });
    await expect(root).toHaveAttribute("data-s7-approval", "AVAILABLE");

    const pageCount = await visualPageCount(page);
    expect(await page.getByLabel("Text content preview").count()).toBe(0);

    const revisionId = new URL(page.url()).pathname.split("/").filter(Boolean).at(-1);
    expect(revisionId).toBeTruthy();
    revisions.push({ revisionId: String(revisionId), pageCount });

    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(page.getByTestId("s7-approved-receipt")).toBeVisible();
    await expect(root).toHaveAttribute("data-s7-approval", "APPROVED");
  }

  expect(new Set(revisions.map((item) => item.revisionId)).size).toBe(4);
  fs.writeFileSync(STATE_FILE, JSON.stringify({ revisions }, null, 2));
  await page.screenshot({ path: "r4-four-post-approved.png", fullPage: true });
});

test("R4 all four approvals and owned visual pages survive backend restart", async ({ page }) => {
  test.setTimeout(120_000);
  const state = JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as { revisions: StoredRevision[] };
  expect(state.revisions).toHaveLength(4);

  const ready = await page.request.get(`${API}/health/ready`);
  expect(ready.ok()).toBeTruthy();
  expect((await ready.json()).status).toBe("READY_DEMO");

  for (const item of state.revisions) {
    await page.goto(`${WEB}/review/${encodeURIComponent(item.revisionId)}`, { waitUntil: "domcontentloaded" });
    const root = page.getByTestId("s5-review-preview");
    await expect(root).toHaveAttribute("data-qa-readiness", "READY_FOR_REVIEW");
    await expect(root).toHaveAttribute("data-s7-approval", "APPROVED");
    await expect(page.getByText("Approved · package frozen", { exact: true })).toBeVisible();
    expect(await visualPageCount(page)).toBe(item.pageCount);
  }

  await page.screenshot({ path: "r4-four-post-after-restart.png", fullPage: true });
});
