import { expect, test } from "@playwright/test";

import { API_URL, SEED, compactWizard, openQueue, openRequestsTab, scanBox, staffLogin, uploadPhoto } from "./helpers";
import { StaffApi, memberApi, rowsOf, unique } from "./r2";

// MOD-1B: the key lending journey from the borrower's side, end to end. The member submits a request through the
// API (account-derived identity), staff work it through the real console (accept -> handover with a box QR scan and
// an issue photo -> return with a photo and a remark), and after every step the member's own status read agrees
// with the screen. Unlike request-lifecycle.spec.ts, which works the seeded pending request, this one creates its
// own row, so it can run on any seeded makerspace in any order.
// Run with `./scripts/dev.sh e2e lending-journey` (needs the seeded dev stack).

type PublicProduct = { id: number; name: string };
type Status = { status: string };

test("a member's request is accepted, issued with QR and photo, and returned with photo and remark", async ({ page, request }) => {
  test.setTimeout(180_000);
  const member = await memberApi(request);
  const catalogue = await request.get(`${API_URL}/api/v1/public/${SEED.slug}/inventory/`);
  expect(catalogue.ok()).toBeTruthy();
  const product = rowsOf<PublicProduct>(await catalogue.json()).find((row) => row.name === SEED.product);
  expect(product, "seeded product missing from the public catalogue").toBeTruthy();

  const label = unique("E2E lending journey");
  const submitted = await member.post<{ public_token: string; status: string }>(`/public/${SEED.slug}/requests`, {
    requested_for: label, items: [{ product_id: product!.id, quantity: 1 }],
  });
  expect(submitted.status).toBe("pending_approval");
  const statusNow = async () => (await member.get<Status>(`/public/requests/${submitted.public_token}/status`)).status;
  expect(await statusNow()).toBe("pending_approval");

  await staffLogin(page);
  await openRequestsTab(page);
  const pending = page.locator("article").filter({ hasText: label }).first();
  await expect(pending).toBeVisible();
  await pending.getByRole("button", { name: "Accept" }).click();
  const acceptDialog = page.getByRole("dialog");
  await acceptDialog.getByRole("button", { name: /^Accept/ }).click();
  await expect(acceptDialog).toBeHidden();
  expect(await statusNow()).toBe("accepted");

  await openQueue(page, "accepted");
  const accepted = page.locator("article").filter({ hasText: label }).first();
  await accepted.getByRole("button", { name: "Start handover" }).click();
  const issueDialog = page.getByRole("dialog");
  await compactWizard(issueDialog);
  const issueConfirm = issueDialog.getByRole("button", { name: "Confirm issue" });
  await expect(issueConfirm).toBeDisabled(); // Hard Rule: no QR scan, no photo, no issue
  await scanBox(issueDialog, SEED.boxCode);
  await issueDialog.getByLabel("I checked the borrower against this request").check();
  await expect(issueConfirm).toBeDisabled(); // still no issue photo
  await uploadPhoto(issueDialog);
  await issueConfirm.click();
  await expect(issueDialog.getByRole("heading", { name: /^Issued to/ })).toBeVisible({ timeout: 20_000 });
  await issueDialog.getByRole("button", { name: "Done" }).click();
  await expect(issueDialog).toBeHidden();
  expect(await statusNow()).toBe("issued");

  await openQueue(page, "active");
  const active = page.locator("article").filter({ hasText: label }).first();
  await expect(active).toBeVisible();
  await active.getByRole("button", { name: "Return", exact: true }).click();
  const returnDialog = page.getByRole("dialog");
  await compactWizard(returnDialog);
  await scanBox(returnDialog, SEED.boxCode);
  await returnDialog.getByLabel("I checked the borrower against this request").check();
  await uploadPhoto(returnDialog);
  await returnDialog.getByLabel("Return remark (required)").fill("Back and checked by the lending journey spec.");
  await returnDialog.getByRole("button", { name: "Confirm return" }).click();
  await expect(returnDialog.getByRole("heading", { name: "Return recorded" }).first()).toBeVisible({ timeout: 20_000 });
  await returnDialog.getByRole("button", { name: "Done" }).click();
  await expect(returnDialog).toBeHidden();

  expect(await statusNow()).toBe("returned");
  const staff = await StaffApi.open(request);
  const active2 = await staff.get<{ results: Array<{ requested_for: string }> }>(`/admin/makerspace/${staff.makerspaceId}/active-loans`);
  expect(active2.results.some((row) => row.requested_for === label)).toBeFalsy();
});
