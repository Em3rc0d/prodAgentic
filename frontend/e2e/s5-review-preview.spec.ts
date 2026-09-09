import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const frontendOrigin = "http://127.0.0.1:3000";
const corsHeaders = {
  "Access-Control-Allow-Origin": frontendOrigin,
  "Access-Control-Allow-Credentials": "true",
};

const goldenRoot = path.resolve(process.env.S5_GOLDEN_OUTPUT_ROOT || "../s5-cert-evidence/goldens");
const manifest = JSON.parse(fs.readFileSync(path.join(goldenRoot, "manifest.json"), "utf8"));
const logan = manifest.goldens.find((item: { line: string }) => item.line === "logan");
if (!logan) throw new Error("S5 Logan golden manifest is missing");

async function installPreviewRoutes(page: Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        authenticated: true,
        auth_enabled: true,
        csrf_token: "s5-cert-csrf-token",
        expires_at: 4102444800,
      }),
    });
  });

  await page.route("**/api/content-revisions/revision-s5-golden/render-preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({
        revision_id: "revision-s5-golden",
        status: "QA_PENDING",
        qa_state: "QA_PENDING",
        format: "carousel",
        alt_text: "Two-page automotive education carousel rendered by the certified S5 Chromium path.",
        assets: logan.pages.map((item: { page_id: string; page_index: number; width: number; height: number; sha256: string }) => ({
          asset_id: `asset-s5-golden-${item.page_index}`,
          page_id: item.page_id,
          page_index: item.page_index,
          width: item.width,
          height: item.height,
          sha256: item.sha256,
          url: `/api/render-assets/asset-s5-golden-${item.page_index}/content`,
        })),
      }),
    });
  });

  for (const item of logan.pages) {
    await page.route(`**/api/render-assets/asset-s5-golden-${item.page_index}/content`, async (route) => {
      const file = path.join(goldenRoot, "logan", `page-${String(item.page_index).padStart(2, "0")}.png`);
      await route.fulfill({
        status: 200,
        contentType: "image/png",
        headers: corsHeaders,
        body: fs.readFileSync(file),
      });
    });
  }
}

async function assertPreview(page: Page, screenshotName: string) {
  const events: string[] = [];
  page.on("console", (message) => events.push(`console:${message.type()}: ${message.text()}`));
  page.on("pageerror", (error) => events.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => events.push(`requestfailed: ${request.method()} ${request.url()} :: ${request.failure()?.errorText ?? "unknown"}`));
  page.on("response", (response) => {
    if (response.url().includes("render-preview") || response.url().includes("/api/auth/session")) {
      events.push(`response: ${response.status()} ${response.url()}`);
    }
  });

  await installPreviewRoutes(page);
  await page.goto(`${frontendOrigin}/review/revision-s5-golden`, { waitUntil: "networkidle" });

  const preview = page.getByTestId("s5-review-preview");
  if ((await preview.count()) === 0) {
    const body = await page.locator("body").innerText().catch(() => "<body unavailable>");
    const html = await page.content().catch(() => "<html unavailable>");
    const suffix = screenshotName.replace(/\.png$/i, "");
    const evidenceRoot = path.resolve("../s5-cert-evidence");
    fs.writeFileSync(
      path.join(evidenceRoot, `${suffix}-diagnostics.txt`),
      [`url=${page.url()}`, "", "EVENTS", ...events, "", "BODY", body, "", "HTML", html].join("\n"),
      "utf8",
    );
    await page.screenshot({ path: path.join(evidenceRoot, `${suffix}-failure.png`), fullPage: true }).catch(() => undefined);
  }

  await expect(preview).toBeVisible();
  await expect(page.getByText("Rendered · QA pending")).toBeVisible();
  await expect(page.getByText("Page 1 of 2 · 1080×1350")).toBeVisible();
  await expect(page.getByRole("button", { name: "Show rendered page 2 of 2" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Approve/i })).toHaveCount(0);

  const image = page.getByRole("img", { name: /automotive education carousel/i });
  await expect(image).toBeVisible();
  expect(await image.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0 && node.naturalHeight > 0)).toBe(true);

  await page.screenshot({ path: path.resolve("../s5-cert-evidence", screenshotName), fullPage: true });
}

test("S5 Review preview displays real Chromium golden on desktop without approval authority", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await assertPreview(page, "review-desktop.png");
});

test("S5 Review preview remains usable on mobile with the same owned golden bytes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await assertPreview(page, "review-mobile.png");
});
