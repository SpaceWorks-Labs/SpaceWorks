import { expect, test } from "@playwright/test";

import {
  StaffApi, blockThirdParty, escapeRegExp, localInput, memberApi, memberArea, pendingEventCharge, rowsOf, staffConsole, unique,
} from "./r2";

// #134 flow 5, refund through a refund case (L24, L5): a member asks for a refund on a charge
// they paid in person, a Space Manager approves it from the Refunds queue and records how the
// money went back (an offline refund receipt), and the member sees the answer. No provider is
// involved: an in-person payment is refunded in person.

type RefundCase = {
  id: number; status: string; approved_amount: string | null; kind: string;
  payment: { id: number; subject_label: string; amount: string; member_name: string };
};
type StaffPayment = { id: number; status: string; refunded_amount: string };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("a member asks for a refund and staff approve it with an in-person refund receipt", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  const member = await memberApi(request);
  const { charge } = await pendingEventCharge(staff, member, "E2E Refundable Workshop", "15.00");
  await staff.post(`/admin/makerspace/${staff.makerspaceId}/payments/${charge.id}/mark-offline`, {
    settlement: { method: "cash", reference: unique("E2E-PAID").replace(/\s+/g, "-"), received_at: new Date(Date.now() - 60_000).toISOString() },
  });

  await test.step("member requests a refund from Payments", async () => {
    await memberArea(page, "payments");
    const row = page.locator("li").filter({ hasText: charge.subject_label });
    await row.getByRole("button", { name: "Request refund" }).click();
    const dialog = page.getByRole("dialog", { name: "Request a refund" });
    await dialog.getByLabel("Why are you asking?").fill("E2E: I can no longer attend.");
    await dialog.getByRole("button", { name: "Send request" }).click();
    await expect(dialog).toBeHidden();
    await expect(row.getByText("Refund under review")).toBeVisible();
  });

  const open = rowsOf(await staff.get<RefundCase[] | { results: RefundCase[] }>(
    `/admin/makerspace/${staff.makerspaceId}/refund-cases?status=open`)).find((row) => row.payment.id === charge.id);
  expect(open, "the request opens a refund case").toBeTruthy();

  await test.step("staff approve it and record the cash going back", async () => {
    const desk = await browser.newContext();
    const deskPage = await desk.newPage();
    await blockThirdParty(deskPage);
    await staffConsole(deskPage, "refunds");
    await expect(deskPage.getByRole("heading", { name: "Refunds", exact: true }).first()).toBeVisible();
    await deskPage.getByRole("button", { name: new RegExp(`· ${escapeRegExp(charge.subject_label)}`) }).click();
    const dialog = deskPage.getByRole("dialog", { name: /^Refund for / });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("radio", { name: "Approve" }).check();
    await dialog.getByLabel("Amount to refund").fill(charge.amount);
    await expect(dialog.getByText("This charge was paid in person, so the money goes back the same way.", { exact: false })).toBeVisible();
    await dialog.getByLabel("Refund method").selectOption({ label: "Cash" });
    await dialog.getByLabel("Refund reference (optional)").fill("E2E-REFUND");
    const returnedAt = dialog.getByLabel("Returned at");
    if (!(await returnedAt.inputValue())) await returnedAt.fill(localInput(new Date(Date.now() - 60_000).toISOString()));
    await dialog.getByRole("button", { name: /^Record .* returned$/ }).click();
    await expect(dialog).toBeHidden();
    await desk.close();
  });

  const decided = (await staff.get<RefundCase>(`/admin/makerspace/${staff.makerspaceId}/refund-cases/${open!.id}`));
  expect(decided.status).toBe("approved");
  expect(Number(decided.approved_amount)).toBe(Number(charge.amount));
  // A fully refunded charge may keep its paid status or move to a refunded one; look in both.
  const payments = async (status: string) => rowsOf(await staff.get<StaffPayment[] | { results: StaffPayment[] }>(
    `/admin/makerspace/${staff.makerspaceId}/payments?status=${status}`));
  const payment = [...await payments("paid_offline"), ...(await staff.call<unknown>("GET",
    `/admin/makerspace/${staff.makerspaceId}/payments?status=refunded`, undefined, false)).status === 200
    ? await payments("refunded") : []].find((row) => row.id === charge.id);
  expect(Number(payment?.refunded_amount)).toBe(Number(charge.amount));

  await test.step("the member sees the approved refund", async () => {
    await page.reload();
    const row = page.locator("li").filter({ hasText: charge.subject_label });
    await expect(row.getByText("Refund approved").first()).toBeVisible();
    await expect(row.getByText(/Refunded .* by cash/i)).toBeVisible();
  });
});
