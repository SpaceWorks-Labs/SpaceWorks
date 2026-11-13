import { expect, test } from "@playwright/test";

import { SEED, staffLogin } from "./helpers";

test.describe("staff authentication", () => {
  test("a wrong password is refused with a visible error", async ({ page }) => {
    await page.goto(`/m/${SEED.slug}/admin`);
    await page.getByLabel("Email", { exact: true }).fill(`${SEED.manager.username}@e2e.local`);
    await page.getByLabel("Password", { exact: true }).fill("not-the-password");
    await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  });

  test("the seeded Space Manager signs in and lands on the console", async ({ page }) => {
    await staffLogin(page);
    await expect(page).toHaveURL(new RegExp(`/m/${SEED.slug}/admin`));
    await expect(page.getByText(SEED.makerspaceName).first()).toBeVisible();
  });
});
