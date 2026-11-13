import { expect, test } from "@playwright/test";

import { API_URL, SEED } from "./helpers";
import {
  StaffApi, blockThirdParty, escapeRegExp, memberApi, memberArea, pendingEventCharge, rowsOf, staffConsole, unique,
} from "./r2";

// #134 flow 4, payment.
//  - Offline: a charge raised with no gateway (provider=unclaimed) is marked paid in person from
//    the staff Payments screen with a ManualSettlement receipt (method, reference, received
//    date), and the member can download the receipt PDF.
//  - Online: with the payments rail on, the member starts a checkout. The provider is never
//    contacted: the checkout session is created server-side, so the spec answers OUR checkout
//    endpoint with a fake hosted-page URL and serves that page itself. Settlement only ever
//    comes from a signed provider webhook, so the charge must still be pending afterwards.

type StaffPayment = {
  id: number; status: string; subject_label: string;
  settlement: { method: string; reference: string; received_at: string } | null;
};
type PaymentDocument = { id: number; payment: number; kind: string; number: string };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("staff record an in-person payment with a receipt, and the member downloads it", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  const member = await memberApi(request);
  const { charge } = await pendingEventCharge(staff, member, "E2E Paid Workshop");
  const reference = unique("E2E-RCPT").replace(/\s+/g, "-");

  await test.step("staff mark the charge paid in person", async () => {
    await staffConsole(page, "payments");
    await expect(page.getByRole("heading", { name: "Payments", exact: true }).first()).toBeVisible();
    const row = page.getByRole("row").filter({ has: page.getByLabel(`Select row ${charge.id}`) });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Mark paid" }).click();
    const dialog = page.getByRole("dialog", { name: "Record payment" });
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("Method").selectOption({ label: "Cash" });
    await dialog.getByLabel("Reference").fill(reference);
    await expect(dialog.getByLabel("Received")).not.toHaveValue("");
    await dialog.getByRole("button", { name: "Save receipt" }).click();
    await expect(dialog).toBeHidden();
    await expect(row).toHaveCount(0);
  });

  const settled = rowsOf(await staff.get<StaffPayment[] | { results: StaffPayment[] }>(
    `/admin/makerspace/${staff.makerspaceId}/payments?status=paid_offline`)).find((row) => row.id === charge.id);
  expect(settled?.status).toBe("paid_offline");
  expect(settled?.settlement?.method).toBe("cash");
  expect(settled?.settlement?.reference).toBe(reference);

  await test.step("the receipt PDF is issued and downloads", async () => {
    let receipt: PaymentDocument | undefined;
    await expect.poll(async () => {
      receipt = rowsOf(await member.get<PaymentDocument[] | { results: PaymentDocument[] }>(
        `/member/makerspaces/${SEED.makerspaceId}/payment-documents`)).find((doc) => doc.payment === charge.id && doc.kind === "receipt");
      return receipt?.id ?? 0;
    }, { message: "billing.documents issues a receipt in the settlement transaction" }).toBeGreaterThan(0);
    const grant = await member.get<{ url: string }>(`/member/makerspaces/${SEED.makerspaceId}/payment-documents/${receipt!.id}/download-url`);
    const pdf = await request.get(new URL(grant.url, API_URL).toString(), { headers: { Authorization: `Bearer ${member.token}` } });
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toContain("application/pdf");
    expect((await pdf.body()).subarray(0, 5).toString("latin1")).toBe("%PDF-");
  });

  await test.step("the member sees how it was paid", async () => {
    const memberContext = await browser.newContext();
    const memberPage = await memberContext.newPage();
    await blockThirdParty(memberPage);
    await memberArea(memberPage, "payments");
    const row = memberPage.locator("li").filter({ hasText: settled!.subject_label });
    await expect(row.getByText(/Received .* by cash/i)).toBeVisible();
    await memberPage.getByRole("button", { name: "Show documents" }).click();
    const documents = memberPage.getByRole("region", { name: "Payment documents" });
    await expect(documents.getByText(new RegExp(`^Receipt `)).first()).toBeVisible();
    const download = memberPage.waitForEvent("download");
    await documents.getByRole("button", { name: "Download PDF" }).first().click();
    expect((await download).suggestedFilename()).toMatch(/^[\w-]+\.pdf$/);
    await memberContext.close();
  });
});

test("online checkout goes to the provider page and waits for the webhook (gateway mocked)", async ({ page, request }) => {
  const staff = await StaffApi.open(request);
  const member = await memberApi(request);
  // Raised while the rail is off, so registering never asks a provider for a session.
  const { charge } = await pendingEventCharge(staff, member, "E2E Online Workshop", "20.00");

  await staff.installModules("payments");
  await staff.setFeatures(["payments.enabled", "payments.events"]);
  try {
    await test.step("placeholder Razorpay credentials make the rail available (format-checked only)", async () => {
      // Not secrets: the format check is local and nothing ever reaches Razorpay in this spec.
      await staff.reauth();
      await staff.patch(`/admin/makerspace/${staff.makerspaceId}/payment-settings`, {
        provider: "razorpay", razorpay_key_id: "rzp_test_E2EPlaceholder",
        razorpay_key_secret: "e2e_placeholder_not_a_secret", razorpay_webhook_secret: "e2e-placeholder-webhook",
      });
      await expect.poll(async () => (await member.get<Array<{ id: number; online_payment_available?: boolean }>>(
        `/member/makerspaces/${SEED.makerspaceId}/payments`)).find((row) => row.id === charge.id)?.online_payment_available)
        .toBe(true);
    });

    const gateway = "https://checkout.gateway.e2e.invalid/pay/e2e-session";
    const checkoutCalls: string[] = [];
    await page.route(/\/api\/v1\/member\/makerspaces\/\d+\/payments\/\d+\/checkout$/, async (route) => {
      checkoutCalls.push(route.request().url());
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ checkout_url: gateway }) });
    });
    await page.route("https://checkout.gateway.e2e.invalid/**", (route) => route.fulfill({
      status: 200, contentType: "text/html",
      body: "<!doctype html><title>E2E gateway</title><h1>E2E fake gateway</h1><p>No money moves here.</p>",
    }));

    await test.step("member starts the checkout and lands on the (fake) hosted page", async () => {
      await memberArea(page, "payments");
      const row = page.locator("li").filter({ hasText: charge.subject_label });
      await row.getByRole("button", { name: "Generate payment link" }).click();
      await expect(page).toHaveURL(gateway);
      await expect(page.getByRole("heading", { name: "E2E fake gateway" })).toBeVisible();
      expect(checkoutCalls).toHaveLength(1);
      expect(checkoutCalls[0]).toMatch(new RegExp(`/payments/${charge.id}/checkout$`));
    });

    await test.step("returning from the provider settles nothing without its webhook", async () => {
      await page.goto(`/m/${SEED.slug}/member/payments?checkout=success`);
      const row = page.locator("li").filter({ hasText: new RegExp(escapeRegExp(charge.subject_label)) });
      await expect(row.getByText("Pending", { exact: true })).toBeVisible();
      const after = (await member.get<Array<{ id: number; status: string }>>(`/member/makerspaces/${SEED.makerspaceId}/payments`))
        .find((row) => row.id === charge.id);
      expect(after?.status).toBe("pending");
    });
  } finally {
    // Other specs raise event charges with the rail off; leave it off for them.
    await staff.setFeatures([], ["payments.events"]);
  }
});
