import { mkdirSync } from "node:fs";
import { expect, Page, test } from "@playwright/test";

const BASE_URL = process.env.UI_CERT_BASE_URL ?? "http://127.0.0.1:3000";
const API_URL = process.env.UI_CERT_API_URL ?? "http://127.0.0.1:8000";
const SCREENSHOT_DIR = "ui-cert-screenshots";

mkdirSync(SCREENSHOT_DIR, { recursive: true });

const ROUTES = [
  { path: "/", title: "Create content", slug: "create" },
  { path: "/library", title: "Content library", slug: "library" },
  { path: "/profiles", title: "Content profiles", slug: "profiles" },
  { path: "/publishing", title: "LinkedIn publishing", slug: "publishing" },
  { path: "/scheduling", title: "Scheduling", slug: "scheduling" },
] as const;

type ViewportName = "desktop" | "mobile";

async function certifyRoute(page: Page, route: (typeof ROUTES)[number], viewportName: ViewportName) {
  const consoleErrors: string[] = [];
  const apiFailures: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().startsWith(API_URL) && response.status() >= 400) {
      apiFailures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (url.startsWith(BASE_URL) || url.startsWith(API_URL)) {
      apiFailures.push(`REQUEST_FAILED ${request.method()} ${url}: ${request.failure()?.errorText ?? "unknown"}`);
    }
  });

  const response = await page.goto(`${BASE_URL}${route.path}`, { waitUntil: "domcontentloaded" });
  expect(response, `${route.path} should return a navigation response`).not.toBeNull();
  expect(response?.ok(), `${route.path} should load successfully`).toBeTruthy();

  await expect(page.getByRole("heading", { level: 1, name: route.title })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Primary product navigation" });
  await expect(nav).toBeVisible();

  // Let client-side API reads settle without depending on provider-backed generation.
  await page.waitForTimeout(650);

  const overlayCount = await page.locator("[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay").count();
  expect(overlayCount, `${route.path} should not render a framework error overlay`).toBe(0);

  const geometry = await page.evaluate(() => {
    const root = document.documentElement;
    const body = document.body;
    return {
      horizontalOverflow: Math.max(root.scrollWidth, body.scrollWidth) - window.innerWidth,
      pageHeight: Math.max(root.scrollHeight, body.scrollHeight),
      viewportHeight: window.innerHeight,
      bodyTextLength: body.innerText.trim().length,
    };
  });

  expect(geometry.bodyTextLength, `${route.path} should render meaningful content`).toBeGreaterThan(80);
  expect(geometry.horizontalOverflow, `${route.path} must not overflow horizontally`).toBeLessThanOrEqual(1);

  if (route.path === "/" && viewportName === "desktop") {
    expect(
      geometry.pageHeight,
      "Create desktop must remain a single-viewport studio; internal panels own any necessary scrolling",
    ).toBeLessThanOrEqual(geometry.viewportHeight + 2);
  }

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
  test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "no-preference" });

  for (const route of ROUTES) {
    test(`${route.slug} desktop`, async ({ page }) => {
      await certifyRoute(page, route, "desktop");
    });
  }
});

test.describe("UI-01-CERT mobile product frames", () => {
  test.use({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });

  for (const route of ROUTES) {
    test(`${route.slug} mobile`, async ({ page }) => {
      await certifyRoute(page, route, "mobile");
    });
  }
});
