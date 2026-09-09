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
const zipFixture = Buffer.from("s8-manual-export-zip-fixture");

async function installApprovedRoutes(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        authenticated: true,
        auth_enabled: true,
        csrf_token: "s8-csrf",
        expires_at: 4102444800,
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s8/render-preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s8",
        status: "REVIEWABLE",
        qa_state: "REVIEWABLE",
        format: "single_image",
        alt_text: "S8 approved visual",
        assets: [{
          asset_id: "asset-s8",
          page_id: "page-0",
          page_index: 0,
          width: 1080,
          height: 1350,
          sha256: "a".repeat(64),
          url: "/api/render-assets/asset-s8/content",
        }],
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s8/qa-evidence", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s8",
        revision_status: "REVIEWABLE",
        readiness: "READY_FOR_REVIEW",
        approval_available: false,
        qa_report: {
          qa_report_id: "qa-s8",
          verdict: "PASS",
          warnings: [],
          failures: [],
          recovery_attempt: 0,
          digest: "b".repeat(64),
        },
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s8/review-authority", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        tenant_id: "tenant-s8",
        content_id: "content-s8",
        revision_id: "revision-s8",
        review_digest: "d".repeat(64),
        revision_status: "REVIEWABLE",
        editorial_state: "APPROVED",
        approval_available: false,
        existing_approval_id: "approval-s8",
        profile_snapshot_digest: "1".repeat(64),
        plan_digest: "2".repeat(64),
        research_digest: "3".repeat(64),
        content_digest: "4".repeat(64),
        visual_spec_digest: "5".repeat(64),
        qa_digest: "6".repeat(64),
        asset_digests: ["a".repeat(64)],
        content: {
          schema_version: 1,
          content_spec_id: "content-spec-s8",
          plan_id: "plan-s8",
          language: "en",
          title: "Manual fallback",
          hook: "Approval should remain useful without a connected channel.",
          body: "Download the exact approved package and publish it manually.",
          cta: "Keep the approval as authority.",
          hashtags: ["#s8"],
          alt_text_draft: "S8 preview",
          format: "single_image",
          format_spec: {
            kind: "single_image",
            headline: "Approval should remain useful without a connected channel.",
            supporting_copy: [],
          },
          claims_used: [],
        },
      }),
    });
  });
  await page.route("**/api/render-assets/asset-s8/content", async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", headers: corsHeaders, body: tinyPng });
  });
}

test("S8 approved Review offers a manual package as a first-class fallback", async ({ page }) => {
  await installApprovedRoutes(page);
  let exportRequests = 0;
  await page.route("**/api/approvals/approval-s8/manual-export", async (route) => {
    exportRequests += 1;
    expect(route.request().method()).toBe("GET");
    await route.fulfill({
      status: 200,
      contentType: "application/zip",
      headers: {
        ...corsHeaders,
        "Content-Disposition": 'attachment; filename="prodagentic-manual-server.zip"',
      },
      body: zipFixture,
    });
  });

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${frontendOrigin}/review/revision-s8`, { waitUntil: "networkidle" });

  const root = page.getByTestId("s5-review-preview");
  await expect(root).toHaveAttribute("data-s7-approval", "APPROVED");
  await expect(root).toHaveAttribute("data-s8-export", "AVAILABLE");
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create revision", exact: true })).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download manual package", exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("prodagentic-manual-approval-s8.zip");
  expect(exportRequests).toBe(1);
});

test("S8 manual export remains reachable on a mobile Review surface", async ({ page }) => {
  await installApprovedRoutes(page);
  await page.route("**/api/approvals/approval-s8/manual-export", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/zip",
      headers: corsHeaders,
      body: zipFixture,
    });
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${frontendOrigin}/review/revision-s8`, { waitUntil: "networkidle" });
  await expect(page.getByRole("button", { name: "Download manual package", exact: true })).toBeVisible();
  await expect(page.getByTestId("s5-review-preview")).toHaveAttribute("data-s8-export", "AVAILABLE");
});
