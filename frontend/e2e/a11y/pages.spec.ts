import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { SEED } from "../helpers";
import { staffConsole } from "../r2";

// TEST-LEVELS: the pages e2e/a11y.spec.ts does not reach (landing, space list, one public item, staff dashboard),
// WCAG 2.1 AA in a real browser, light and dark. Added as a new file so the existing spec stays untouched.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectClean(page: Page) {
  // The dashboard fires a few dozen widget requests; on a dev stack they need more than the default 10 s.
  await expect(page.locator('[aria-label^="Loading"]')).toHaveCount(0, { timeout: 45_000 });
  await expect(page.locator("p").filter({ hasText: /^Loading / })).toHaveCount(0);
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const summary = results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join("\n");
  expect(results.violations, summary).toEqual([]);
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} accessibility, more pages`, () => {
    test.use({ colorScheme });
    // Dev-stack pages can take a while to settle (dozens of widget requests); the checks wait up to 45 s.
    test.describe.configure({ timeout: 120_000 });

    test("space landing page", async ({ page }) => {
      await page.goto(`/m/${SEED.slug}`);
      await expect(page.getByRole("heading").first()).toBeVisible();
      await expectClean(page);
    });

    test("platform landing / space list", async ({ page }) => {
      await page.goto("/");
      await expect(page.locator("main, [role=main], body").first()).toBeVisible();
      await expect(page.getByRole("heading").first()).toBeVisible();
      await expectClean(page);
    });

    test("public item page", async ({ page }) => {
      await page.goto(`/m/${SEED.slug}/inventory`);
      // The first plain-text match is a screen-reader-only "Open details for ..." span; the visible name is exact.
      await page.getByText(SEED.product, { exact: true }).first().click();
      await expect(page.getByRole("heading", { name: SEED.product }).first()).toBeVisible();
      await expectClean(page);
    });

    test("staff dashboard", async ({ page }) => {
      await staffConsole(page);
      await expect(page.locator("[data-app-shell]")).toBeVisible();
      await expectClean(page);
    });
  });
}
