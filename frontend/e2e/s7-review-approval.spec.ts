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
const reviewDigest = "d".repeat(64);

async function installRoutes(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json", headers: corsHeaders,
      body: JSON.stringify({ authenticated: true, auth_enabled: true, csrf_token: "s7-csrf", expires_at: 4102444800 }),
    });
  });
  await page.route("**/api/content-revisions/revision-s7/render-preview", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json", headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s7", status: "REVIEWABLE", qa_state: "REVIEWABLE", format: "single_image",
        alt_text: "S7 review visual", assets: [{
          asset_id: "asset-s7", page_id: "page-0", page_index: 0, width: 1080, height: 1350,
          sha256: "a".repeat(64), url: "/api/render-assets/asset-s7/content",
        }],
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s7/qa-evidence", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json", headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s7", revision_status: "REVIEWABLE", readiness: "READY_FOR_REVIEW",
        approval_available: false,
        qa_report: { qa_report_id: "qa-s7", verdict: "PASS", warnings: [], failures: [], recovery_attempt: 0, digest: "b".repeat(64) },
      }),
    });
  });
  await page.route("**/api/content-revisions/revision-s7/review-authority", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json", headers: corsHeaders,
      body: JSON.stringify({
        tenant_id: "tenant-s7", content_id: "content-s7", revision_id: "revision-s7",
        review_digest: reviewDigest, revision_status: "REVIEWABLE", editorial_state: "READY_FOR_REVIEW",
        approval_available: true, existing_approval_id: null,
        profile_snapshot_digest: "1".repeat(64), plan_digest: "2".repeat(64), research_digest: "3".repeat(64),
        content_digest: "4".repeat(64), visual_spec_digest: "5".repeat(64), qa_digest: "6".repeat(64),
        asset_digests: ["a".repeat(64)],
        content: {
          schema_version: 1, content_spec_id: "content-spec-s7", plan_id: "plan-s7", language: "en",
          title: "Governed Review", hook: "Approve the exact package", body: "Review the content, not the pipeline.",
          cta: "Inspect details only when needed.", hashtags: ["#s7"], alt_text_draft: "S7 preview",
          format: "single_image", format_spec: { kind: "single_image", headline: "Approve the exact package", supporting_copy: [] },
          claims_used: [],
        },
      }),
    });
  });
  await page.route("**/api/render-assets/asset-s7/content", async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", headers: corsHeaders, body: tinyPng });
  });
}

test("S7 Review exposes deliberate Approve and freezes exact package", async ({ page }) => {
  await installRoutes(page);
  await page.route("**/api/content-revisions/revision-s7/approve", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    expect(body.expected_review_digest).toBe(reviewDigest);
    await route.fulfill({
      status: 201, contentType: "application/json", headers: corsHeaders,
      body: JSON.stringify({ approval: {
        approval_id: "approval-s7", content_id: "content-s7", revision_id: "revision-s7",
        bundle_sha256: "f".repeat(64), approved_by: "operator-s7", approved_at: "2026-09-09T11:00:00Z",
      }, next_stage: "S8_EXPORT_PACKAGE" }),
    });
  });

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${frontendOrigin}/review/revision-s7`, { waitUntil: "networkidle" });
  const root = page.getByTestId("s5-review-preview");
  await expect(root).toHaveAttribute("data-s7-approval", "AVAILABLE");
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeVisible();
  await expect(page.getByText("Review the content, not the pipeline.")).toBeVisible();
  await expect(page.getByText("qa-s7")).not.toBeVisible();
  await page.getByText("Why / Details").click();
  await expect(page.getByText("qa-s7")).toBeVisible();

  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByTestId("s7-approved-receipt")).toContainText("Approved · exact content package frozen");
  await expect(page.getByTestId("s7-approved-receipt")).toContainText("approval-s7");
  await expect(root).toHaveAttribute("data-s7-approval", "APPROVED");
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create revision", exact: true })).toBeVisible();
});

test("S7 Edit forks a new revision rather than mutating reviewed content", async ({ page }) => {
  await installRoutes(page);
  await page.route("**/api/content-revisions/revision-s7/edit", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    expect(body.expected_review_digest).toBe(reviewDigest);
    expect(body.edited_content.content_spec_id).not.toBe("content-spec-s7");
    expect(body.edited_content.body).toBe("Human revised caption.");
    await route.fulfill({
      status: 201, contentType: "application/json", headers: corsHeaders,
      body: JSON.stringify({
        revision: { revision_id: "revision-s7-edit" }, visual_reused: true,
        invalidated: ["QAReport", "Approval", "Assets"], next_stage: "S4_OR_S5_BY_INVALIDATION_FRONTIER",
      }),
    });
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${frontendOrigin}/review/revision-s7`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByRole("textbox", { name: "Caption or body" }).fill("Human revised caption.");
  await page.getByRole("button", { name: "Save as new revision" }).click();
  const receipt = page.getByTestId("s7-edit-receipt");
  await expect(receipt).toContainText("New revision created");
  await expect(receipt.getByRole("link")).toHaveAttribute("href", "/review/revision-s7-edit");
});
