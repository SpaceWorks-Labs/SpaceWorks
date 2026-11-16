import { expect, test } from "@playwright/test";

import { SEED, apiGet, apiLogin, apiPost, compactWizard, makerspaceId, openQueue, scanBox, staffLogin, uploadPhoto } from "./helpers";

// The Hard Rules from CLAUDE.md, pinned where they are enforced: the API refuses, and the
// console refuses before it even asks the API.
test.describe("hard rules", () => {
  test("the console will not submit an issue without a container code or photo", async ({ page }) => {
    await staffLogin(page);
    await openQueue(page, "accepted");
    // The seed leaves a second, already-accepted request for this probe so the lifecycle spec
    // and this one never compete for the same row.
    const row = page.locator("article").filter({ hasText: SEED.probeRequestFor }).first();
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Start handover" }).click();
    const dialog = page.getByRole("dialog");
    await compactWizard(dialog);
    const confirm = dialog.getByRole("button", { name: "Confirm issue" });
    // Nothing scanned, no borrower check, no photo: the wizard keeps the confirm button disabled.
    await expect(confirm).toBeDisabled();
    await scanBox(dialog, SEED.boxCode);
    await dialog.getByLabel("I checked the borrower against this request").check();
    await expect(confirm).toBeDisabled(); // still no issue photo
    await uploadPhoto(dialog);
    await expect(confirm).toBeEnabled();
    await expect(dialog).toBeVisible();
  });

  test("the API refuses an issue without evidence and a return without a remark", async ({ request }) => {
    const token = await apiLogin(request, SEED.manager.username, SEED.manager.password);
    const id = await makerspaceId(request, token);
    const accepted = await apiGet<{ results: Array<{ id: number }> }>(request, token, `/admin/makerspace/${id}/accepted-requests`);
    const pending = await apiGet<{ results: Array<{ id: number }> }>(request, token, `/admin/makerspace/${id}/pending-requests`);
    const target = accepted.results[0] ?? pending.results[0];
    test.skip(!target, "no seeded request left to exercise");

    const noEvidence = await apiPost(request, token, `/admin/requests/${target.id}/issue`, {
      box_code: SEED.boxCode,
      remark: "attempting without a photo",
    });
    expect(noEvidence.status()).toBe(400);
    const body = await noEvidence.text();
    expect(body).toMatch(/evidence/i);

    const noBox = await apiPost(request, token, `/admin/requests/${target.id}/issue`, {
      evidence_id: 999_999,
      remark: "attempting without a box",
    });
    expect(noBox.status()).toBe(400);

    const active = await apiGet<{ results: Array<{ id: number }> }>(request, token, `/admin/makerspace/${id}/active-loans`);
    if (active.results[0]) {
      const noRemark = await apiPost(request, token, `/admin/requests/${active.results[0].id}/return`, {
        evidence_id: 999_999,
        remark: "",
        resolutions: [],
      });
      expect(noRemark.status()).toBe(400);
    }
  });
});
