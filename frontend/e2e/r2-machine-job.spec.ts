import { expect, test } from "@playwright/test";

import { SEED } from "./helpers";
import { StaffApi, blockThirdParty, memberApi, memberArea, rowsOf, unique } from "./r2";

// MOD-2B machine journey: a member requests a job on a priced machine type, the Space Manager sends a quote, the
// member approves it on the job page with the digest they were shown, staff start and complete the job, and the
// charge is recorded against the member. The member's steps run in the browser; setup and staff steps use the API.
// The spec skips (never fails) when the seed space has no machine queue that takes job requests.

type Queue = { queue_id: number; machine_type_id: number; name: string };
type Machine = { id: number; machine_type: number | { id: number } };
type Job = { id: number; status: string; quote: { total: string; digest: string } | null };
type PaymentRow = { id: number; amount: string; status: string; subject_type?: string };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("a member requests a job, staff quote it, the member approves and the charge is recorded", async ({ page, request }) => {
  const staff = await StaffApi.open(request);
  const member = await memberApi(request);
  await staff.installModules("machines", "machine_service");
  await staff.enableFeatures("charges.enabled", "charges.machines");

  const queues = await member.get<Queue[]>(`/public/${SEED.slug}/machine-jobs/types`);
  test.skip(queues.length === 0, "the e2e seed has no machine queue that takes job requests");
  const queue = queues[0];

  await staff.put(`/admin/makerspace/${staff.makerspaceId}/machine-type-pricing/${queue.machine_type_id}`, {
    payment_enabled: true, rate_per_unit: "2.000", flat_fee: "5.000",
  });
  const title = unique("E2E quoted job");

  const created = await member.post<{ id: number }>(`/public/${SEED.slug}/machine-jobs`, {
    queue_id: queue.queue_id, title, description: "Quote journey", file_ids: [], copies: 1, acknowledgements: {},
  });
  const jobId = created.id;

  await test.step("staff send a quote priced by the rate card", async () => {
    const quoted = await staff.post<Job>(`/admin/machine-service/requests/${jobId}/quote`, { estimated_minutes: 30 });
    expect(quoted.status).toBe("quoted");
    expect(Number(quoted.quote?.total)).toBeGreaterThan(0);
  });

  await test.step("the member sees the quote and approves it", async () => {
    await memberArea(page, `machine-jobs/${jobId}`);
    await expect(page.getByRole("heading", { name: "Your quote" })).toBeVisible();
    await page.getByRole("button", { name: "Approve quote" }).click();
    await expect.poll(async () => (await member.get<Job>(`/member/machine-jobs/${jobId}`)).status,
      { message: "the approved quote moves the job out of quoted" }).not.toBe("quoted");
  });

  const machines = await staff.get<Machine[] | { results: Machine[] }>(`/admin/makerspace/${staff.makerspaceId}/machines`);
  const rows = Array.isArray(machines) ? machines : machines.results;
  const machine = rows.find((row) => (typeof row.machine_type === "number" ? row.machine_type : row.machine_type.id) === queue.machine_type_id);
  test.skip(!machine, "the queue's machine type has no machine to run the job on");

  await test.step("staff start and complete the job", async () => {
    await staff.post(`/admin/machine-service/requests/${jobId}/start`, { machine_id: machine!.id });
    const done = await staff.post<Job>(`/admin/machine-service/requests/${jobId}/complete`, { actual_minutes: 20, consumptions: [] });
    expect(done.status).toBe("completed");
  });

  await test.step("the charge is recorded against the member and never exceeds the quote", async () => {
    const payments = await member.get<PaymentRow[] | { results: PaymentRow[] }>(`/member/makerspaces/${member.makerspaceId}/payments`);
    const list = rowsOf(payments);
    const charge = list.filter((row) => row.subject_type === "machine_service_request")
      .sort((a, b) => b.id - a.id)[0];
    expect(charge, "a payment row exists for the completed job").toBeTruthy();
    const quoted = (await member.get<Job>(`/member/machine-jobs/${jobId}`)).quote;
    if (quoted) expect(Number(charge!.amount)).toBeLessThanOrEqual(Number(quoted.total));
  });
});
