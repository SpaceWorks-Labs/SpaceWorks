import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

import { SEED } from "./helpers";
import { StaffApi, blockThirdParty, memberApi, memberArea, rowsOf, unique } from "./r2";

// seed_e2e exports this dedicated fixture in .seed.json. Keep the schema local to
// this journey so other lanes' shared e2e helpers do not need to change.
type MachineSeed = { queue_id: number; machine_type_id: number; machine_id: number };
function machineSeed(): MachineSeed {
  const path = process.env.E2E_SEED_FILE ?? fileURLToPath(new URL("./.seed.json", import.meta.url));
  const seeded = JSON.parse(readFileSync(path, "utf8")) as { slug: string; machine_journey?: MachineSeed };
  expect(seeded.slug).toBe(SEED.slug);
  expect(seeded.machine_journey, "run the standard seed_e2e command to provision the machine journey").toBeDefined();
  return seeded.machine_journey!;
}
type Queue = { queue_id: number; machine_type_id: number; is_printer: boolean };
type Job = { id: number; status: string; title: string; quote: { total: string; currency: string; digest: string } | null };
type Charge = { id: number; subject_type: string; subject_id: number; amount: string; currency: string; status: string };
type OwnCharge = { id: number; amount: string; status: string; online_payment_available: boolean };
type Upload = { file_id: number; upload: { url: string; method?: string; headers?: Record<string, string>; fields?: Record<string, string> } };

// A binary STL with one triangle: the real maker_formats validator checks its declared count and size.
function triangle(): Buffer {
  const bytes = Buffer.alloc(134);
  bytes.write("SpaceWorks CX5 machine journey", 0, "ascii");
  bytes.writeUInt32LE(1, 80);
  bytes.writeFloatLE(1, 92); // normal z
  bytes.writeFloatLE(1, 108); // vertex 2 x
  bytes.writeFloatLE(1, 124); // vertex 3 y
  return bytes;
}

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("member requests a service, staff quote, member approves, completion records exactly one charge", async ({ page, request }) => {
  test.setTimeout(180_000);
  const staff = await StaffApi.open(request);
  const member = await memberApi(request);
  await staff.installModules("machines", "machine_service", "membership", "presence");
  await staff.setFeatures(["machines.job_requests", "machines.job_quotes", "charges.enabled", "charges.machines"],
    ["payments.machines", "charges.pricing", "charges.discounts", "billing.tax"]);

  const fixture = machineSeed();
  const queues = await member.get<Queue[]>(`/public/${SEED.slug}/machine-jobs/types`);
  const queue = queues.find((row) => row.queue_id === fixture.queue_id);
  expect(queue, "the dedicated seeded queue must be active and accepting job requests").toBeDefined();
  expect(queue).toMatchObject({ machine_type_id: fixture.machine_type_id, is_printer: false });
  const typeId = fixture.machine_type_id;
  const machineType = await staff.get<{ capability_config: { metering_unit?: string; requires_booking?: boolean } }>(
    `/admin/makerspace/${staff.makerspaceId}/machine-types/${typeId}`);
  expect(machineType.capability_config.metering_unit, "the seeded service type must meter minutes").toBe("minutes");
  expect(machineType.capability_config.requires_booking, "service fixture must allow staff to run without a booking").toBe(false);
  await staff.put(`/admin/makerspaces/${staff.makerspaceId}/machine-types/${typeId}/job-settings`, {
    accepts_job_requests: true, file_groups: ["fab-3dprint"], quote_mode: "always", payment_timing: "completion",
  });
  await staff.put(`/admin/makerspace/${staff.makerspaceId}/machine-type-pricing/${typeId}`, {
    payment_enabled: true, rate_per_unit: "2.000", flat_fee: "5.000",
  });
  const machine = await staff.get<{ id: number; machine_type: { id: number }; status: string; open_to_all_members: boolean }>(
    `/admin/machines/${fixture.machine_id}`);
  expect(machine).toMatchObject({ id: fixture.machine_id, machine_type: { id: typeId }, status: "idle", open_to_all_members: true });
  const membership = await staff.membershipOf();
  await staff.post(`/admin/makerspace/${staff.makerspaceId}/presence-sessions/check-in`, {
    account_id: membership.user.id, status: "visiting", duration_minutes: 120,
  });
  const title = unique("E2E machine journey");
  let jobId = 0;
  let quotedTotal = "";
  let currency = "";

  await test.step("member uploads a design and submits the service request", async () => {
    const staged = await member.post<Upload>(`/public/${SEED.slug}/machine-jobs/uploads`, {
      queue_id: queue!.queue_id, filename: "triangle.stl", content_type: "model/stl", kind: "model",
    });
    const upload = staged.upload;
    const response = upload.method === "PUT"
      ? await request.put(upload.url, { data: triangle(), headers: upload.headers })
      : await request.post(upload.url, { multipart: {
        ...upload.fields, file: { name: "triangle.stl", mimeType: "model/stl", buffer: triangle() },
      } });
    expect(response.ok(), await response.text()).toBe(true);
    const created = await member.post<Job>(`/public/${SEED.slug}/machine-jobs`, {
      queue_id: queue!.queue_id, title, description: "A staged, validated design for the quote journey.",
      file_ids: [staged.file_id], copies: 1,
      acknowledgements: { pickup_policy: true, failure_policy: true, own_content: true },
    });
    expect(created.status).toBe("pending");
    jobId = created.id;
  });

  await test.step("staff quote and the member approves the shown price in the browser", async () => {
    await staff.post(`/admin/machine-service/requests/${jobId}/quote`, { estimated_minutes: 30 });
    const quoted = await member.get<Job>(`/member/machine-jobs/${jobId}`);
    expect(quoted.status).toBe("quoted");
    expect(quoted.quote).toMatchObject({ total: "65.00", currency: "usd" });
    quotedTotal = quoted.quote!.total;
    currency = quoted.quote!.currency;
    await memberArea(page, `machine-jobs/${jobId}`);
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your quote" })).toBeVisible();
    const approval = page.waitForResponse((response) =>
      response.url().endsWith(`/member/machine-jobs/${jobId}/approve-quote`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Approve quote", exact: true }).click();
    const approved = await approval;
    expect(approved.status()).toBe(200);
    expect(approved.request().postDataJSON()).toEqual({ digest: quoted.quote!.digest });
    await expect.poll(async () => (await member.get<Job>(`/member/machine-jobs/${jobId}`)).status).toBe("accepted");
    await expect(page.getByRole("button", { name: "Approve quote", exact: true })).toHaveCount(0);
  });

  await test.step("staff run the job and completion records the member's exact debt", async () => {
    const started = await staff.post<Job>(`/admin/machine-service/requests/${jobId}/start`, { machine_id: machine.id });
    expect(started.status).toBe("in_progress");
    const completed = await staff.post<Job>(`/admin/machine-service/requests/${jobId}/complete`, {
      actual_minutes: 20, consumptions: [],
    });
    expect(completed.status).toBe("completed");
    expect((await member.get<Job>(`/member/machine-jobs/${jobId}`)).status).toBe("completed");
    const charges = async () => rowsOf(await staff.get<Charge[] | { results: Charge[] }>(
      `/admin/makerspace/${staff.makerspaceId}/payments`)).filter((row) =>
      row.subject_type === "machine_service_request" && row.subject_id === jobId);
    const recorded = await charges();
    expect(recorded).toHaveLength(1);
    expect(recorded[0]).toMatchObject({ amount: "45.00", currency, status: "pending" });
    expect(Number(recorded[0].amount)).toBeLessThanOrEqual(Number(quotedTotal));
    const replay = await staff.call<{ code: string }>("POST", `/admin/machine-service/requests/${jobId}/complete`,
      { actual_minutes: 20, consumptions: [] }, false);
    expect(replay.status).toBe(409);
    expect(replay.body.code).toBe("service_invalid_transition");
    expect(await charges()).toEqual(recorded);
    const own = rowsOf(await member.get<OwnCharge[] | { results: OwnCharge[] }>(
      `/member/makerspaces/${member.makerspaceId}/payments`)).filter((row) => row.id === recorded[0].id);
    expect(own).toHaveLength(1);
    expect(own[0]).toMatchObject({ amount: "45.00", status: "pending", online_payment_available: false });
  });
});
