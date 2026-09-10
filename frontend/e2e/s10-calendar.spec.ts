import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:3000";
const cors = {
  "Access-Control-Allow-Origin": origin,
  "Access-Control-Allow-Credentials": "true",
};

async function installBase(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: cors,
      body: JSON.stringify({
        authenticated: true,
        auth_enabled: true,
        csrf_token: "s10-csrf",
        expires_at: 4102444800,
      }),
    });
  });
  await page.route("**/api/calendar", async (route) => {
    const now = new Date();
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: cors,
      body: JSON.stringify({
        start_at: new Date(now.getTime() - 86400000).toISOString(),
        end_at: new Date(now.getTime() + 36 * 86400000).toISOString(),
        capability: {
          provider: "linkedin",
          connected: true,
          can_publish: true,
          supports_text: true,
          supports_single_image: true,
          supports_multi_image: false,
          can_reconcile: true,
          external_identity: "urn:li:person:s10",
          api_version: "202608",
          observed_at: now.toISOString(),
          reason: null,
        },
        manual_export_fallback: true,
        entries: [
          {
            kind: "approval",
            schedule_id: null,
            approval_id: "approval-s10-ready",
            content_id: "System design post",
            provider: "linkedin",
            destination: "member_feed",
            scheduled_for: null,
            approved_at: now.toISOString(),
            timezone_context: null,
            state: "APPROVED_UNSCHEDULED",
            publication_id: null,
            reconciliation_reason: null,
            safe_error: null,
            asset_count: 1,
          },
          {
            kind: "schedule",
            schedule_id: "schedule-s10-reconcile",
            approval_id: "approval-s10-reconcile",
            provider: "linkedin",
            destination: "member_feed|urn:li:person:s10",
            scheduled_for: tomorrow.toISOString(),
            timezone_context: "America/Lima",
            state: "RECONCILIATION_REQUIRED",
            publication_id: "pub-s10-reconcile",
            reconciliation_reason: "Provider success may have occurred; automatic replay blocked",
            safe_error: null,
          },
        ],
      }),
    });
  });
}

test("S10 Calendar exposes Week Month Queue, scheduling intent and reconciliation without blind retry", async ({ page }) => {
  await installBase(page);
  let scheduleBody: Record<string, unknown> | null = null;
  let reconciles = 0;
  await page.route("**/api/approvals/approval-s10-ready/schedules", async (route) => {
    scheduleBody = route.request().postDataJSON();
    await route.fulfill({ status: 201, contentType: "application/json", headers: cors, body: JSON.stringify({ schedule: {} }) });
  });
  await page.route("**/api/publications/pub-s10-reconcile/reconcile", async (route) => {
    reconciles += 1;
    await route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ state: "RECONCILIATION_REQUIRED" }) });
  });
  await page.route("**/api/approvals/approval-s10-ready/manual-export", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/zip", headers: cors, body: "manual-s10" });
  });

  await page.setViewportSize({ width: 1365, height: 900 });
  await page.goto(`${origin}/calendar`, { waitUntil: "networkidle" });

  const root = page.getByTestId("s10-calendar");
  await expect(root).toHaveAttribute("data-view", "week");
  await expect(page.getByRole("heading", { name: "Calendar" })).toBeVisible();
  await expect(page.getByText("LinkedIn connected")).toBeVisible();
  await expect(page.getByText("Needs reconciliation")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download manual package" })).toBeVisible();

  await page.getByRole("button", { name: "Month" }).click();
  await expect(root).toHaveAttribute("data-view", "month");
  await page.getByRole("button", { name: "Queue" }).click();
  await expect(root).toHaveAttribute("data-view", "queue");

  await page.getByRole("button", { name: "Schedule on LinkedIn" }).click();
  const dialog = page.getByRole("dialog", { name: "Choose the local publishing time" });
  await expect(dialog).toBeVisible();
  const local = new Date(Date.now() + 2 * 86400000);
  const value = `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, "0")}-${String(local.getDate()).padStart(2, "0")}T${String(local.getHours()).padStart(2, "0")}:${String(local.getMinutes()).padStart(2, "0")}`;
  await dialog.getByLabel("Local date and time").fill(value);
  await dialog.getByRole("button", { name: "Schedule approved content" }).click();
  await expect.poll(() => scheduleBody).not.toBeNull();
  expect(typeof scheduleBody?.scheduled_for).toBe("string");
  expect(typeof scheduleBody?.timezone_context).toBe("string");
  expect(String(scheduleBody?.timezone_context).length).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Reconcile evidence" }).click();
  await expect.poll(() => reconciles).toBe(1);
});

test("S10 Calendar is usable on mobile without horizontal overflow", async ({ page }) => {
  await installBase(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/calendar`, { waitUntil: "networkidle" });

  await expect(page.getByRole("button", { name: "Week" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Month" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Queue" })).toBeVisible();
  await expect(page.getByText("Approved · unscheduled")).toBeVisible();
  await expect(page.getByText("Needs reconciliation")).toBeVisible();
  const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  expect(noOverflow).toBe(true);
});
