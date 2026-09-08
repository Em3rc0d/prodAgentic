import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const goldenRoot = path.resolve(process.env.S5_GOLDEN_OUTPUT_ROOT || "../s5-cert-evidence/goldens");
const manifest = JSON.parse(fs.readFileSync(path.join(goldenRoot, "manifest.json"), "utf8"));
const logan = manifest.goldens.find((item: { line: string }) => item.line === "logan");
if (!logan) throw new Error("S5 Logan golden manifest is missing");

async function installPreviewRoutes(page: Page) {
  await page.route("**/api/content-revisions/revision-s5-golden/render-preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
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
      await route.fulfill({ status: 200, contentType: "image/png", body: fs.readFileSync(file) });
    });
  }
}

async function assertPreview(page: Page, screenshotName: string) {
  await installPreviewRoutes(page);
  await page.goto("http://127.0.0.1:3000/review/revision-s5-golden", { waitUntil: "networkidle" });

  await expect(page.getByTestId("s5-review-preview")).toBeVisible();
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
