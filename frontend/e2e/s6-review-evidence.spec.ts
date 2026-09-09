import { expect, test } from "@playwright/test";

const frontendOrigin = "http://127.0.0.1:3000";
const corsHeaders = {
  "Access-Control-Allow-Origin": frontendOrigin,
  "Access-Control-Allow-Credentials": "true",
};
const tinyPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlN0V8AAAAASUVORK5CYII=",
  "base64",
);

async function installS6Routes(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        authenticated: true,
        auth_enabled: true,
        csrf_token: "s6-cert-csrf-token",
        expires_at: 4102444800,
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s6-reviewable/render-preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s6-reviewable",
        status: "REVIEWABLE",
        qa_state: "REVIEWABLE",
        format: "single_image",
        alt_text: "S6 certified rendered preview",
        assets: [{
          asset_id: "asset-s6-reviewable",
          page_id: "page-0",
          page_index: 0,
          width: 1080,
          height: 1350,
          sha256: "a".repeat(64),
          url: "/api/render-assets/asset-s6-reviewable/content",
        }],
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s6-reviewable/qa-evidence", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s6-reviewable",
        revision_status: "REVIEWABLE",
        readiness: "READY_FOR_REVIEW",
        approval_available: false,
        qa_report: {
          qa_report_id: "qa-s6-reviewable",
          verdict: "PASS",
          warnings: [],
          failures: [],
          recovery_attempt: 1,
          digest: "b".repeat(64),
        },
      }),
    });
  });
  await page.route("**/api/render-assets/asset-s6-reviewable/content", async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", headers: corsHeaders, body: tinyPng });
  });
}

test("S6 Review consumes QA evidence and exposes reviewability without approval authority", async ({ page }) => {
  await installS6Routes(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${frontendOrigin}/review/revision-s6-reviewable`, { waitUntil: "networkidle" });

  const preview = page.getByTestId("s5-review-preview");
  await expect(preview).toBeVisible();
  await expect(preview).toHaveAttribute("data-qa-readiness", "READY_FOR_REVIEW");
  await expect(page.getByText("Ready for review")).toBeVisible();
  await expect(page.getByText("PASS", { exact: true })).toBeVisible();
  await page.getByText("QA evidence", { exact: true }).last().click();
  await expect(page.getByText("qa-s6-reviewable")).toBeVisible();
  await expect(page.getByRole("button", { name: /Approve/i })).toHaveCount(0);
});
