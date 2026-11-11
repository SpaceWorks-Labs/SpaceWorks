import { expect, test } from "@playwright/test";

import { API_URL, EVIDENCE_FIXTURE, SEED } from "./helpers";
import { MEMBER, StaffApi, blockThirdParty, memberArea, rowsOf, staffConsole, unique } from "./r2";

// #134 flow 7, ID card (L3 + GAP3): staff issue the member card from the console and email it,
// the print PDF renders, the member adds a consented card photo and opens the public check
// page from My cards, and the check page shows the card valid, then not valid once revoked.
//
// There is no member-side "request" step for the member card: staff issue it, or it is issued
// when a membership starts. The request -> approve flow belongs to organisation ID programmes
// (membership.id_programmes), which need an organisation the e2e seed does not create; see
// R2-FLOWS.md.

type Card = { id: number; card_number: string; printed_name: string; membership_id: number; is_active: boolean; photo_set: boolean };
type Settings = { public_verify: boolean; email_available: boolean };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("staff issue and email a member card; the member adds a photo and the public check page verifies it", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  await staff.installModules("membership");
  // The check-link token is minted at issue time only if the public check is already on.
  const settings = await staff.put<Settings>(`/admin/makerspaces/${staff.makerspaceId}/member-card-settings`, {
    public_verify: true, email_on_issue: false, design_approval_required: false,
  });
  expect(settings.public_verify).toBe(true);
  expect(settings.email_available, "the email module must be on to email cards").toBe(true);
  const membership = await staff.membershipOf(MEMBER);
  const activeCards = async () => rowsOf(await staff.get<Card[] | { results: Card[] }>(
    `/admin/makerspaces/${staff.makerspaceId}/member-cards?status=active`)).filter((card) => card.membership_id === membership.id);
  // An earlier run leaves an active card; revoke it so the member is back on the issue roster.
  for (const card of await activeCards()) {
    await staff.post(`/admin/member-cards/${card.id}/revoke`, { note: "E2E reset before re-issue" });
  }
  const printedName = unique("E2E Card Holder");
  const holder = membership.user.display_name || membership.user.username;

  await test.step("staff issue the card from the Issue tab", async () => {
    await staffConsole(page, "member-cards");
    await expect(page.getByRole("heading", { name: "Member cards" }).first()).toBeVisible();
    await page.getByRole("tab", { name: "Issue", exact: true }).click();
    const roster = page.getByRole("region", { name: "Members without a card" });
    const nameField = roster.getByLabel(`Printed name for ${holder}`, { exact: true });
    await nameField.fill(printedName);
    // The innermost block holding the field also holds its own "Issue card" button.
    await roster.locator("div").filter({ has: nameField }).last().getByRole("button", { name: "Issue card" }).click();
    await expect(nameField).toHaveCount(0);
  });

  const [card] = (await activeCards()).filter((row) => row.printed_name === printedName);
  expect(card, "the issued card is active").toBeTruthy();

  await test.step("staff email the card from the Cards tab", async () => {
    await page.getByRole("tab", { name: "Cards", exact: true }).click();
    await page.getByRole("button", { name: `Actions for ${printedName}` }).click();
    await page.getByRole("menuitem", { name: "Email card" }).click();
    await expect(page.getByText(`Card emailed to ${printedName}.`)).toBeVisible();
  });

  await test.step("the print PDF renders", async () => {
    const pdf = await request.post(`${API_URL}/api/v1/admin/member-cards/${card.id}/print.pdf`, {
      headers: { Authorization: `Bearer ${staff.token}` },
    });
    expect(pdf.status()).toBe(200);
    expect((await pdf.body()).subarray(0, 5).toString("latin1")).toBe("%PDF-");
  });

  const memberContext = await browser.newContext();
  const memberPage = await memberContext.newPage();
  await blockThirdParty(memberPage);

  await test.step("the member uploads a card photo with consent (GAP3)", async () => {
    await memberArea(memberPage, "account-portal?section=card");
    await expect(memberPage.getByRole("heading", { name: "Your member card" })).toBeVisible();
    await memberPage.getByLabel("Choose a photo").setInputFiles(EVIDENCE_FIXTURE);
    await memberPage.getByLabel(/^I agree to my photo being stored privately/).check();
    await memberPage.getByRole("button", { name: "Upload photo" }).click();
    await expect(memberPage.getByText("Photo uploaded.")).toBeVisible({ timeout: 20_000 });
    await expect.poll(async () => (await activeCards()).find((row) => row.id === card.id)?.photo_set).toBe(true);
  });

  let token = "";
  await test.step("My cards links to the public check page", async () => {
    await memberPage.goto(`/m/${SEED.slug}/member/cards`);
    const section = memberPage.getByRole("region", { name: /^Member card, / }).first();
    await expect(section.getByText("Valid", { exact: true })).toBeVisible();
    const href = await section.getByRole("link", { name: "Check page" }).getAttribute("href");
    token = href?.match(/\/verify\/c\/([^/?#]+)/)?.[1] ?? "";
    expect(token, `check link ${href}`).not.toBe("");
  });
  await memberContext.close();

  await test.step("anyone can check the card: valid", async () => {
    const check = await browser.newContext();
    const checkPage = await check.newPage();
    await blockThirdParty(checkPage);
    await checkPage.goto(`/verify/c/${token}`);
    await expect(checkPage.getByRole("heading", { name: "This card is valid" })).toBeVisible();
    await expect(checkPage.getByText("Checked just now.")).toBeVisible();
    await expect(checkPage.getByText(card.card_number).first()).toBeVisible();

    await test.step("and not valid once revoked", async () => {
      await staff.post(`/admin/member-cards/${card.id}/revoke`, { note: "E2E: card reported lost" });
      await checkPage.getByRole("button", { name: "Check again" }).click();
      await expect(checkPage.getByRole("heading", { name: "This card is not valid" })).toBeVisible();
      await expect(checkPage.getByText("Do not accept this card.")).toBeVisible();
    });
    await check.close();
  });

  const verdict = await request.get(`${API_URL}/api/v1/public/card-verifications/${token}`);
  expect(verdict.status()).toBe(200);
  expect(((await verdict.json()) as { status: string; valid: boolean }).valid).toBe(false);
});
