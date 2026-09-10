import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:3000";
const cors = {
  "Access-Control-Allow-Origin": origin,
  "Access-Control-Allow-Credentials": "true",
};

async function installAuth(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: cors,
      body: JSON.stringify({
        authenticated: true,
        auth_enabled: true,
        csrf_token: "s11-csrf",
        expires_at: 4102444800,
      }),
    });
  });
}

function snapshot(now: Date) {
  return {
    schema_version: 1,
    metric_snapshot_id: "metric_s11",
    operation_key: "a".repeat(64),
    tenant_id: "tenant-s11",
    publication_id: "pub-s11",
    provider: "linkedin",
    external_post_id: "urn:li:share:999",
    captured_at: now.toISOString(),
    raw_available_metrics: {
      IMPRESSION: 1280,
      REACTION: 34,
      COMMENT: 9,
      RESHARE: 4,
    },
    normalized_metrics: {
      views_or_impressions: 1280,
      likes_or_reactions: 34,
      comments: 9,
      shares: 4,
    },
    unavailable_metrics: ["MEMBERS_REACHED"],
    freshness: {
      observed_at: now.toISOString(),
      expected_next_sync_at: new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString(),
      policy_version: "linkedin-member-post-lifecycle-v1",
    },
    source_version: "linkedin-member-post-v1",
    provider_api_version: "202608",
    collection_bucket: "t+24h",
    raw_digest: "b".repeat(64),
    snapshot_digest: "c".repeat(64),
    created_at: now.toISOString(),
  };
}

async function installOverview(
  page: import("@playwright/test").Page,
  options: { scope?: boolean; stale?: boolean } = {},
) {
  const now = new Date();
  const captured = options.stale
    ? new Date(now.getTime() - 96 * 60 * 60 * 1000)
    : new Date(now.getTime() - 2 * 60 * 60 * 1000);
  await page.route("**/api/analytics/overview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: cors,
      body: JSON.stringify({
        published_content_count: 3,
        measured_publication_count: 1,
        normalized_totals: {
          views_or_impressions: 1280,
          likes_or_reactions: 34,
          comments: 9,
          shares: 4,
        },
        coverage: {
          views_or_impressions: 1,
          likes_or_reactions: 1,
          comments: 1,
          shares: 1,
        },
        impressions_or_views: 1280,
        impressions_coverage_count: 1,
        interactions: 47,
        interaction_coverage: {
          likes_or_reactions: 1,
          comments: 1,
          shares: 1,
        },
        last_success_at: captured.toISOString(),
        freshness_state: options.stale ? "STALE" : "FRESH",
        analytics_policy_version: "linkedin-member-post-lifecycle-v1",
        automatic_collection_enabled: true,
        capability: {
          schema_version: 1,
          provider: "linkedin",
          connected: true,
          analytics_available: options.scope !== false,
          analytics_scope_granted: options.scope !== false,
          supported_provider_metrics: ["IMPRESSION", "MEMBERS_REACHED", "RESHARE", "REACTION", "COMMENT"],
          external_identity: "urn:li:person:s11",
          api_version: "202608",
          observed_at: now.toISOString(),
          last_success_at: captured.toISOString(),
          reason: options.scope === false ? "LinkedIn analytics permission is not granted" : null,
        },
        latest_snapshots: [snapshot(captured)],
      }),
    });
  });
}

test("S11 Analytics renders evidence coverage unavailable metrics and stale freshness honestly", async ({ page }) => {
  await installAuth(page);
  await installOverview(page, { stale: true });
  let collections = 0;
  await page.route("**/api/analytics/publications/pub-s11/collect", async (route) => {
    collections += 1;
    await route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ status: "QUEUED" }) });
  });

  await page.setViewportSize({ width: 1365, height: 900 });
  await page.goto(`${origin}/analytics`, { waitUntil: "networkidle" });

  const root = page.getByTestId("s11-analytics");
  await expect(root).toHaveAttribute("data-freshness", "STALE");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByText("Evidence for better decisions", { exact: false })).toBeVisible();
  await expect(page.getByText("1,280").first()).toBeVisible();
  await expect(page.getByText("Members Reached")).toBeVisible();
  await expect(page.getByText("Unavailable")).toBeVisible();
  await expect(page.getByText(/Stale ·/)).toBeVisible();
  await expect(page.getByText("0", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Collect fresh snapshot" }).click();
  await expect.poll(() => collections).toBe(1);
});

test("S11 Analytics keeps publishing connection usable while analytics permission is missing", async ({ page }) => {
  await installAuth(page);
  await installOverview(page, { scope: false });
  let upgrades = 0;
  await page.route("**/api/connections/linkedin/analytics/enable", async (route) => {
    upgrades += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: cors,
      body: JSON.stringify({ authorization_url: `${origin}/analytics?oauth=upgrade`, requested_scope: "r_member_postAnalytics" }),
    });
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`${origin}/analytics`, { waitUntil: "networkidle" });
  await expect(page.getByText("Permission needed")).toBeVisible();
  await expect(page.getByText("LinkedIn analytics permission is not granted")).toBeVisible();
  await page.getByRole("button", { name: "Enable analytics" }).click();
  await expect.poll(() => upgrades).toBe(1);
});

test("S11 Analytics remains usable on mobile without horizontal overflow", async ({ page }) => {
  await installAuth(page);
  await installOverview(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/analytics`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByText("Publication evidence")).toBeVisible();
  await expect(page.getByText("Unavailable")).toBeVisible();
  const noOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  expect(noOverflow).toBe(true);
});
