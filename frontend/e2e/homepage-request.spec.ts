import { expect, test, type Page } from "@playwright/test";
import { API_URL, SEED } from "./helpers";
import { MEMBER, submitSignIn } from "./r2";

type PublicSpace = { slug: string; name: string };
async function publicState(page: Page) {
  const config = await page.request.get(`${API_URL}/api/v1/config`);
  expect(config.ok()).toBeTruthy();
  const spaces = await page.request.get(`${API_URL}/api/public/makerspaces/`);
  expect(spaces.ok()).toBeTruthy();
  return { enabled: (await config.json()).landing_enabled !== false, spaces: await spaces.json() as PublicSpace[] };
}
async function hubLinks(page: Page) {
  for (const href of ["/docs", "/features", "/spaces", "https://github.com/SpaceWorks-Labs/SpaceWorks"]) {
    await expect(page.locator(`a[href="${href}"]:visible`).first()).toBeVisible();
  }
}
// Fresh-install coverage is intentionally run against an empty deployment, without replacing real API responses.
test("a fresh deployment shows the landing", async ({ page }) => {
  const state = await publicState(page);
  test.skip(!state.enabled || state.spaces.length !== 0, "Requires a fresh deployment with landing enabled and no public spaces");
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Run the space, not spreadsheets." })).toBeVisible();
  await hubLinks(page);
});
test("the homepage selects the only space or directory, with sign-in and hub links", async ({ page }) => {
  const { spaces, enabled } = await publicState(page);
  expect(spaces.length, "Run seed_e2e before the seeded homepage tests").toBeGreaterThan(0);
  await page.goto("/");
  if (spaces.length === 1) await expect(page).toHaveURL(new RegExp(`/m/${spaces[0].slug}$`));
  else {
    await expect(page.getByRole("heading", { level: 1, name: "Find a makerspace near you" })).toBeVisible();
    const search = page.getByRole("searchbox", { name: "Search spaces" });
    if (await search.count()) await search.fill(SEED.makerspaceName);
    await expect(page.locator(`a[href="/m/${SEED.slug}"]`)).toBeVisible();
  }
  await hubLinks(page);
  await expect(page.getByRole("link", { name: "Sign in", exact: true }).first()).toBeVisible();
  if (enabled) {
    await page.locator('a[href="/about"]:visible').first().click();
    await expect(page.getByRole("heading", { level: 1, name: "Run the space, not spreadsheets." })).toBeVisible();
  }
});
for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
  test(`signed-out item Request returns from sign-in with quantity (${viewport.width}px)`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/");
    // /spaces remains available even when / redirects to the only makerspace.
    await page.locator('a[href="/spaces"]:visible').first().click();
    const search = page.getByRole("searchbox", { name: "Search spaces" });
    if (await search.count()) await search.fill(SEED.makerspaceName);
    await page.locator(`a[href="/m/${SEED.slug}"]`).click();
    await expect(page).toHaveURL(new RegExp(`/m/${SEED.slug}$`));
    await page.getByRole("link", { name: "Browse inventory", exact: true }).click();
    await page.getByRole("link", { name: SEED.product, exact: true }).click();
    const itemUrl = page.url();
    if (viewport.width < 768) await page.getByRole("button", { name: "Request", exact: true }).click();
    await page.getByRole("spinbutton", { name: "Quantity" }).fill("2");
    await page.getByRole("link", { name: "Sign in to borrow" }).click();
    await submitSignIn(page, MEMBER);
    await expect(page).toHaveURL(itemUrl);
    await expect(page.getByRole("spinbutton", { name: "Quantity" })).toHaveValue("2");
    await expect(page.getByLabel("Request purpose")).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign in to borrow" })).toHaveCount(0);
  });
}
