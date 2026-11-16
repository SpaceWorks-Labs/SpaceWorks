import { expect, test } from "@playwright/test";

import { SEED } from "./helpers";
import { MEMBER, StaffApi, blockThirdParty, isoIn, localInput, memberApi, memberArea, rowsOf, staffConsole, unique } from "./r2";

// #134 flow 1, book a room: a signed-in member requests a slot on the public bookings page, a
// Space Manager approves it from the queue, and a room taken out of service (L16) refuses new
// bookings. Every run makes its own room, so runs never share slots.

type Space = { id: number; name: string; public_token: string };
type BookingRow = { id: number; status: string; space_id: number; space_name: string; starts_at: string };

async function approvalRoom(staff: StaffApi, label: string): Promise<Space> {
  await staff.installModules("bookings", "membership");
  const space = await staff.post<Space>(`/admin/makerspaces/${staff.makerspaceId}/spaces/`, {
    name: unique(label), kind: "meeting", is_public: true, capacity: 6, location: "E2E floor",
  });
  // The create API defaults to instant booking; this flow is the reviewed one.
  await staff.patch(`/admin/spaces/${space.id}/booking-rules/`, { approval_mode: "approve" });
  return space;
}

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("a member requests a slot and the Space Manager approves it", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  const room = await approvalRoom(staff, "E2E Review Room");
  // Tomorrow plus a margin, clear of the 60-minute lead time and inside the 30-day window.
  const startsAt = isoIn(26, 0);
  const endsAt = isoIn(27, 0);

  await test.step("member submits the booking request", async () => {
    await memberArea(page);
    await page.goto(`/m/${SEED.slug}/bookings?space=${room.public_token}`);
    const panel = page.getByRole("complementary", { name: "Choose a time" });
    await expect(panel.getByRole("heading", { name: "Request this space" })).toBeVisible();
    await panel.getByLabel("Starts").fill(localInput(startsAt));
    await panel.getByLabel("Ends").fill(localInput(endsAt));
    await panel.getByRole("button", { name: "Submit booking request" }).click();
    await expect(page.getByRole("heading", { name: "Booking request received" })).toBeVisible();
    await expect(page.getByText("Staff must approve this request before the slot is confirmed.")).toBeVisible();
  });

  const pending = rowsOf(await staff.get<BookingRow[] | { results: BookingRow[] }>(
    `/admin/makerspaces/${staff.makerspaceId}/bookings/?status=pending&page=1&ordering=created_at`))
    .find((row) => row.space_id === room.id);
  expect(pending, "the request is waiting in the staff queue").toBeTruthy();

  await test.step("Space Manager approves it from the queue", async () => {
    const staffContext = await browser.newContext();
    const staffPage = await staffContext.newPage();
    await blockThirdParty(staffPage);
    await staffConsole(staffPage, "bookings");
    await expect(staffPage.getByRole("heading", { name: /^Requests \(\d+\)$/ })).toBeVisible();
    const row = staffPage.locator("li").filter({ hasText: room.name });
    await expect(row).toHaveCount(1);
    await row.getByRole("button", { name: "Approve" }).click();
    await expect(row).toHaveCount(0);
    await staffContext.close();
  });

  const confirmed = rowsOf(await staff.get<BookingRow[] | { results: BookingRow[] }>(`/admin/spaces/${room.id}/bookings/?status=confirmed`));
  expect(confirmed.map((row) => row.id)).toContain(pending!.id);

  await test.step("the member sees it in My bookings", async () => {
    await page.goto(`/m/${SEED.slug}/member/bookings`);
    await expect(page.getByRole("heading", { name: "My bookings" })).toBeVisible();
    await expect(page.getByText(room.name).first()).toBeVisible();
  });
});

test("a room taken out of service refuses new bookings (L16)", async ({ page, request }) => {
  const staff = await StaffApi.open(request);
  const room = await approvalRoom(staff, "E2E Outage Room");
  // The service-state endpoint answers 404 capability_disabled without one of these.
  await staff.enableFeatures("bookings.room_maintenance");
  const outage = await staff.post<{ state: string; outage_id: number }>(`/admin/makerspaces/${staff.makerspaceId}/service-state`, {
    subject_type: "bookable_space", subject_id: room.id, in_service: false,
    reason: "E2E: ceiling leak", expected_back_at: null, mode: "block", issue_id: null,
  });
  expect(outage.state).toBe("out_of_service:block");

  try {
    const startsAt = isoIn(30, 0);
    const endsAt = isoIn(31, 0);

    await test.step("the booking API refuses with the outage reason", async () => {
      const member = await memberApi(request, MEMBER);
      const refused = await member.call<{ detail: string; code: string }>("POST",
        `/public/${SEED.slug}/spaces/${room.public_token}/book/`, { starts_at: startsAt, ends_at: endsAt, website: "" }, false);
      expect(refused.status).toBe(409);
      expect(refused.body.code).toBe("booking_conflict");
      expect(refused.body.detail).toBe("This room is out of service for that time.");
    });

    await test.step("the public form shows the refusal and books nothing", async () => {
      await blockThirdParty(page);
      await memberArea(page);
      await page.goto(`/m/${SEED.slug}/bookings?space=${room.public_token}`);
      const panel = page.getByRole("complementary", { name: "Choose a time" });
      await panel.getByLabel("Starts").fill(localInput(startsAt));
      await panel.getByLabel("Ends").fill(localInput(endsAt));
      await panel.getByRole("button", { name: "Submit booking request" }).click();
      // The form shows one message for every 409; the API step above pins the exact reason.
      await expect(page.getByRole("alert").filter({ hasText: "That time now overlaps a confirmed booking." })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Booking request received" })).toHaveCount(0);
    });

    const rows = rowsOf(await staff.get<BookingRow[] | { results: BookingRow[] }>(`/admin/spaces/${room.id}/bookings/`));
    expect(rows).toHaveLength(0);
  } finally {
    // Back in service, so a re-run on the same seed starts clean (the room itself is unique).
    await staff.post(`/admin/makerspaces/${staff.makerspaceId}/service-state`, {
      subject_type: "bookable_space", subject_id: room.id, in_service: true, issue_id: null,
    });
  }
});
