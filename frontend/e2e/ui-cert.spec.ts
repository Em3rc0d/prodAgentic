import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

const BASE_URL = process.env.UI_CERT_BASE_URL || "http://127.0.0.1:3000";
const API_URL = process.env.UI_CERT_API_URL || "http://127.0.0.1:8000";
const SCREENSHOT_DIR = process.env.UI_CERT_SCREENSHOT_DIR || "ui-cert-screenshots";

const ROUTES = [
  { path: "/", slug: "create", heading: /Create/i },
  { path: "/library", slug: "library", heading: /Library/i },
  { path: "/profiles", slug: "profiles", heading: /Profiles/i },
  { path: "/publishing", slug: "publishing", heading: /Publishing/i },
  { path: "/scheduling", slug: "scheduling", heading: /Scheduling/i },
] as const;

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

test.beforeEach(async ({ context }) => {
  await context.route(`${API_URL}/api/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (url.pathname === "/api/auth/session") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ authenticated: true, auth_enabled: false, csrf_token: null }),
      });
    }

    return route.continue();
  });
});

async function certifyRoute(
  page: Page,
  route: (typeof ROUTES)[number],
  viewportName: "desktop" | "mobile",
) {
  const consoleErrors: string[] = [];
  const apiFailures: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    const requestUrl = response.url();
    if (
      (requestUrl.startsWith(API_URL) || requestUrl.startsWith(`${BASE_URL}/api/`)) &&
      response.status() >= 400
    ) {
      apiFailures.push(`${response.status()} ${requestUrl}`);
    }
  });

  await page.goto(`${BASE_URL}${route.path}`, { waitUntil: "networkidle" });
  await expect(page.locator("body")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("heading", { name: route.heading }).first()).toBeVisible();

  const dimensions = await page.evaluate(() => ({
    bodyScrollWidth: document.body.scrollWidth,
    bodyClientWidth: document.body.clientWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    documentClientWidth: document.documentElement.clientWidth,
  }));
  expect(
    Math.max(dimensions.bodyScrollWidth, dimensions.documentScrollWidth),
    `${route.path} should not overflow the viewport horizontally`,
  ).toBeLessThanOrEqual(
    Math.max(dimensions.bodyClientWidth, dimensions.documentClientWidth) + 1,
  );

  const nav = page.getByRole("navigation", { name: "Primary product navigation" }).first();
  await expect(nav).toBeVisible();
  const navBox = await nav.boundingBox();
  expect(navBox, "Product navigation should have a measurable box").not.toBeNull();
  if (navBox) {
    expect(navBox.x).toBeGreaterThanOrEqual(0);
    expect(navBox.y).toBeGreaterThanOrEqual(0);
    expect(navBox.x + navBox.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
    expect(navBox.y + navBox.height).toBeLessThanOrEqual(page.viewportSize()!.height + 1);
  }

  expect(apiFailures, `${route.path} should not produce failing app/API requests`).toEqual([]);
  expect(consoleErrors, `${route.path} should not emit browser console errors`).toEqual([]);

  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${viewportName}-${route.slug}.png`,
    fullPage: route.path !== "/" || viewportName === "mobile",
  });
}

test.describe("UI-01-CERT desktop product frames", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  for (const route of ROUTES) {
    test(`${route.slug} desktop`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "no-preference" });
      await certifyRoute(page, route, "desktop");
    });
  }
});

test.describe("UI-01-CERT mobile product frames", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const route of ROUTES) {
    test(`${route.slug} mobile`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await certifyRoute(page, route, "mobile");
    });
  }
});
