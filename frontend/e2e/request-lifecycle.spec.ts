import { expect, test } from "@playwright/test";

import { SEED, apiGet, apiLogin, compactWizard, makerspaceId, openQueue, openRequestsTab, scanBox, staffLogin, uploadPhoto } from "./helpers";

// The whole loan spine through the real UI, real presigned upload to object storage and the
// real state machine: pending -> accepted -> issued (box code + photo) -> returned (photo +
// remark). Runs on a freshly seeded makerspace (`manage.py seed_e2e --reset`).
test("accept, issue with box code and photo, then return with photo and remark", async ({ page, request }) => {
  await staffLogin(page);
  await openRequestsTab(page);

  const pending = page.locator("article").filter({ hasText: SEED.pendingRequestFor }).first();
  await expect(pending).toBeVisible();
  await pending.getByRole("button", { name: "Accept" }).click();
  const acceptDialog = page.getByRole("dialog");
  await acceptDialog.getByRole("button", { name: /^Accept/ }).click();
  await expect(acceptDialog).toBeHidden();

  await openQueue(page, "accepted");
  const accepted = page.locator("article").filter({ hasText: SEED.pendingRequestFor }).first();
  await accepted.getByRole("button", { name: "Start handover" }).click();
  const issueDialog = page.getByRole("dialog");
  await compactWizard(issueDialog);
  await scanBox(issueDialog, SEED.boxCode);
  await issueDialog.getByLabel("I checked the borrower against this request").check();
  await uploadPhoto(issueDialog);
  await issueDialog.getByRole("button", { name: "Confirm issue" }).click();
  await expect(issueDialog.getByRole("heading", { name: /^Issued to/ })).toBeVisible({ timeout: 20_000 });
  await issueDialog.getByRole("button", { name: "Done" }).click();
  await expect(issueDialog).toBeHidden();

  await openQueue(page, "active");
  const active = page.locator("article").filter({ hasText: SEED.pendingRequestFor }).first();
  await expect(active).toBeVisible();
  await active.getByRole("button", { name: "Return", exact: true }).click();
  const returnDialog = page.getByRole("dialog");
  // A return re-identifies the container too, so the box is scanned again.
  await compactWizard(returnDialog);
  await scanBox(returnDialog, SEED.boxCode);
  await returnDialog.getByLabel("I checked the borrower against this request").check();
  await uploadPhoto(returnDialog);
  await returnDialog.getByLabel("Return remark (required)").fill("All items back, checked by e2e.");
  await returnDialog.getByRole("button", { name: "Confirm return" }).click();
  await expect(returnDialog.getByRole("heading", { name: "Return recorded" }).first()).toBeVisible({ timeout: 20_000 });
  await returnDialog.getByRole("button", { name: "Done" }).click();
  await expect(returnDialog).toBeHidden();

  // The API is the source of truth for the transition, not the screen.
  const token = await apiLogin(request, SEED.manager.username, SEED.manager.password);
  const id = await makerspaceId(request, token);
  const loans = await apiGet<{ results: Array<{ requested_for: string }> }>(request, token, `/admin/makerspace/${id}/active-loans`);
  expect(loans.results.some((row) => row.requested_for === SEED.pendingRequestFor)).toBeFalsy();
  const acceptedQueue = await apiGet<{ results: Array<{ requested_for: string }> }>(request, token, `/admin/makerspace/${id}/accepted-requests`);
  expect(acceptedQueue.results.some((row) => row.requested_for === SEED.pendingRequestFor)).toBeFalsy();
});
