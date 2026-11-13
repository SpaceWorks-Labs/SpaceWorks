import { expect, test } from "@playwright/test";

import {
  StaffApi, blockThirdParty, memberApi, pendingEventCharge, rowsOf, staffConsole,
} from "./r2";

// Flow audit (decision 470): money owed with the online rail OFF is core ledger data. Switching the
// charging module (Events) off while a registration charge is still owed must neither hide nor change the
// debt: the member still reads it, staff still see it on the Payments screen and can settle it in person,
// and switching Events back on changes nothing. Mirrors backend/tests/modules/test_flow_audit_money_lifecycle.py.
// Not run here: the e2e tooling is owned by LIVE-PASS-2 (run with `./scripts/dev.sh e2e flow-audit`).

type MemberPayment = { id: number; status: string; subject_type: string; amount: string };
type StaffPayment = { id: number; status: string };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("an owed event charge survives Events going off and on, and staff can still settle it", async ({ page, request }) => {
  test.setTimeout(120_000);
  const staff = await StaffApi.open(request);
  const member = await memberApi(request);
  const { charge } = await pendingEventCharge(staff, member, "E2E Flow Audit Workshop");
  const memberPayments = async () => rowsOf(await member.get<MemberPayment[] | { results: MemberPayment[] }>(
    `/member/makerspaces/${member.makerspaceId}/payments`));
  const owed = async () => (await memberPayments()).find((row) => row.id === charge.id);

  try {
    await staff.post(`/admin/makerspace/${staff.makerspaceId}/modules/uninstall`, { key: "events" });
    // The debt is unchanged and still visible to the person who owes it.
    const whileOff = await owed();
    expect(whileOff?.status).toBe("pending");
    expect(whileOff?.amount).toBe(charge.amount);

    await test.step("staff still see it on the Payments screen", async () => {
      await staffConsole(page, "payments");
      await expect(page.getByRole("heading", { name: "Payments", exact: true }).first()).toBeVisible();
      await expect(page.getByRole("row").filter({ has: page.getByLabel(`Select row ${charge.id}`) })).toBeVisible();
    });
  } finally {
    await staff.installModules("events");
  }

  const back = await owed();
  expect(back?.status).toBe("pending");
  expect(back?.amount).toBe(charge.amount);
  const staffRows = rowsOf(await staff.get<StaffPayment[] | { results: StaffPayment[] }>(
    `/admin/makerspace/${staff.makerspaceId}/payments?status=pending`));
  expect(staffRows.filter((row) => row.id === charge.id)).toHaveLength(1); // no duplicate debt after the round trip
});
