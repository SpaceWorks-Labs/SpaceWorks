import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { SEED, openRequestsTab, staffLogin } from "./helpers";
import { MEMBER, StaffApi, submitSignIn } from "./r2";

// WCAG 2.1 AA in a real browser (colour contrast included, which jsdom cannot compute).
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectClean(page: Page) {
  // The shell keeps one empty sr-only live region for announcements; only an alert with text is an error.
  await expect(page.locator('[role="alert"]:not(:empty)')).toHaveCount(0);
  await expect(page.locator('[aria-label^="Loading"]')).toHaveCount(0, { timeout: 45_000 });
  await expect(page.locator("p").filter({ hasText: /^Loading / })).toHaveCount(0);
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const summary = results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join("\n");
  expect(results.violations, summary).toEqual([]);
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} accessibility`, () => {
    test.use({ colorScheme });
    // Dev-stack pages can take a while to settle (dozens of widget requests); the checks wait up to 45 s.
    test.describe.configure({ timeout: 120_000 });

    test("public catalogue and support footer", async ({ page }) => {
      await page.goto(`/m/${SEED.slug}/inventory`);
      await expect(page.getByText(SEED.product).first()).toBeVisible();
      await expect(page.getByRole("link", { name: "Contact support" })).toBeVisible();
      await expectClean(page);
    });

    test("staff login", async ({ page }) => {
      await page.goto(`/m/${SEED.slug}/admin`);
      await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
      await expectClean(page);
    });

    test("staff requests console", async ({ page }) => {
      await staffLogin(page);
      await openRequestsTab(page);
      await expectClean(page);
    });

    test("public events and registration form", async ({ page }) => {
      await page.goto(`/m/${SEED.slug}/events`);
      await expect(page.getByRole("heading", { name: SEED.eventTitle })).toBeVisible();
      await expectClean(page);
      // The list card links to the event page, where Register sits beside the sign-in requirement.
      await page.locator("article").filter({ hasText: SEED.eventTitle }).getByRole("link", { name: "Register", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Join this event" })).toBeVisible();
      await expectClean(page);
      // Registering signed out is refused with a spoken, visible reason (an alert by design), not a silent failure.
      await page.getByRole("button", { name: "Register", exact: true }).click();
      await expect(page.getByRole("alert").filter({ hasText: "Sign in to register for this event." })).toBeVisible();
      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(results.violations.map((v) => v.id)).toEqual([]);
    });

    test("public bookings and request form", async ({ page }) => {
      await page.goto(`/m/${SEED.slug}/bookings`);
      // Each bookable space is a card button (several spaces share the page), not a heading.
      await expect(page.getByRole("button", { name: new RegExp(SEED.bookableSpace) })).toBeVisible();
      await expectClean(page);
      await page.getByRole("button", { name: "Choose a time" }).first().click();
      await expect(page.getByRole("button", { name: "Close booking form" })).toBeVisible();
      await expectClean(page);
    });

    test("member joining screen, sign in and active member area", async ({ page, request }) => {
      // Presence is an opt-in module; the seed does not install it, so the Presence panel needs it on.
      const staff = await StaffApi.open(request);
      await staff.installModules("presence");
      try {
        await page.goto(`/m/${SEED.slug}/member`);
        await expect(page.getByRole("button", { name: "Sign in to join" })).toBeVisible();
        await expectClean(page);
        await page.getByRole("button", { name: "Sign in to join" }).click();
        await expect(page.getByRole("heading", { name: "Member sign in" })).toBeVisible();
        await expectClean(page);
        await submitSignIn(page, MEMBER);
        await expect(page.getByRole("heading", { name: "Membership", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Presence", exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "Contact support" })).toBeVisible();
        await expectClean(page);
      } finally {
        // Presence changes who may request hardware; leave the shared e2e space as it was found.
        await staff.post(`/admin/makerspace/${staff.makerspaceId}/modules/uninstall`, { key: "presence" });
      }
    });

    for (const [path, heading, content] of [
      ["dashboard", "Dashboard", ""],
      ["inventory", "Inventory", SEED.product],
      ["members", "Members", ""],
      ["machines", "Machines", ""],
      ["events", "Events", SEED.eventTitle],
      ["bookings", "Bookings", ""],  // the Requests tab opens first; spaces sit under the Spaces tab
      ["settings", "Makerspace settings", ""],
    ]) {
      test(`staff ${path} panel`, async ({ page }) => {
        await staffLogin(page);
        await page.goto(`/m/${SEED.slug}/admin/${path}`);
        await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
        if (content) await expect(page.getByText(content, { exact: true }).first()).toBeVisible();
        await expectClean(page);
      });
    }
  });
}
