import { expect, test } from "@playwright/test";

import { SEED } from "./helpers";
import {
  E2E_PHONE, StaffApi, blockThirdParty, memberApi, memberArea, publishedEvent, rowsOf, staffConsole, unique,
} from "./r2";

// #134 flow 2, event registration: a member registers on the public event page, gets a ticket
// with a check-in code, and the desk checks them in. The second test is the L6 ticket shop: a
// free ticket ordered through the order flow, and a paid seat that is held until it is paid.

type ActivityRow = { registration_id: number; checkin_token: string | null; event_title: string; status: string };
type RegistrationRow = { id: number; status: string };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("a member registers, opens the ticket, and the desk checks them in", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  await staff.installModules("events", "membership");
  // With events.orders on, a members-audience event shows the ticket shop instead of the form.
  await staff.setFeatures([], ["events.orders"]);
  const event = await publishedEvent(staff, unique("E2E Soldering Night"), { capacity: 8 });

  await test.step("member registers on the event page", async () => {
    await memberArea(page);
    await page.goto(`/m/${SEED.slug}/events/${event.public_token}`);
    const card = page.getByRole("complementary", { name: "Join this event" });
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "Register", exact: true }).click();
    // The seeded member has no phone on the account: the server asks for one on the first try.
    const phone = card.getByLabel("Contact phone");
    const received = page.getByRole("heading", { name: "Registration received" });
    await expect(phone.or(received)).toBeVisible();
    if (await phone.isVisible()) {
      await phone.fill(E2E_PHONE);
      await card.getByRole("button", { name: "Register", exact: true }).click();
    }
    await expect(received).toBeVisible();
    await expect(page.getByText("Registered", { exact: true }).first()).toBeVisible();
  });

  const member = await memberApi(request);
  const activity = await member.get<{ event_registrations: ActivityRow[] }>(`/member/makerspaces/${SEED.makerspaceId}/activity`);
  const mine = activity.event_registrations.find((row) => row.event_title === event.title);
  expect(mine?.checkin_token, "the registration carries a check-in code").toBeTruthy();

  await test.step("the member's ticket shows the check-in QR", async () => {
    await page.goto(`/m/${SEED.slug}/member/events/${mine!.registration_id}/ticket`);
    await expect(page.getByRole("heading", { name: "Your event ticket" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Download ticket PNG" })).toBeVisible();
  });

  await test.step("the desk finds the code and confirms attendance", async () => {
    const desk = await browser.newContext();
    const deskPage = await desk.newPage();
    await blockThirdParty(deskPage);
    await staffConsole(deskPage, `events?event=${event.id}&eventTab=checkin`);
    await deskPage.getByRole("button", { name: "Scan online" }).click();
    await deskPage.getByLabel("Find a guest by check-in code").fill(mine!.checkin_token!);
    await deskPage.getByRole("button", { name: "Find", exact: true }).click();
    await deskPage.getByRole("button", { name: "Confirm attendance" }).click();
    await expect(deskPage.getByText(/checked in\.$/).first()).toBeVisible();
    await expect(deskPage.getByRole("button", { name: "Scan another" })).toBeVisible();
    await desk.close();
  });

  const roster = rowsOf(await staff.get<RegistrationRow[] | { results: RegistrationRow[] }>(`/admin/events/${event.id}/registrations/`));
  expect(roster.find((row) => row.id === mine!.registration_id)?.status).toBe("attended");
});

test("L6 tickets: a free ticket is ordered through the shop, a paid seat is held until paid", async ({ page, request }) => {
  const staff = await StaffApi.open(request);
  await staff.installModules("events", "membership");
  await staff.setFeatures(
    ["events.ticket_types", "events.orders", "events.seat_holds", "charges.enabled", "charges.events"],
    ["billing.maker_checker", "payments.events"],
  );
  const event = await publishedEvent(staff, unique("E2E Robot Arena"), { capacity: 10 });
  const free = await staff.post<{ id: number; name: string }>(`/admin/events/${event.id}/ticket-types/`, {
    name: "E2E free pass", amount: "0.00", capacity: 5,
  });
  const paid = await staff.post<{ id: number; name: string }>(`/admin/events/${event.id}/ticket-types/`, {
    name: "E2E paid seat", amount: "12.00", capacity: 5,
  });

  await test.step("member orders the free ticket through the ticket shop", async () => {
    await memberArea(page);
    await page.goto(`/m/${SEED.slug}/events/${event.public_token}`);
    const tickets = page.getByRole("list", { name: "Tickets" });
    await expect(tickets).toBeVisible();
    await tickets.getByRole("button", { name: `More ${free.name}` }).click();
    await page.getByRole("button", { name: "Review order" }).click();
    const summary = page.getByRole("region", { name: "Order summary" });
    await expect(summary.getByRole("heading", { name: "Your order" })).toBeVisible();
    await page.getByRole("button", { name: "Confirm order" }).click();
    await expect(page).toHaveURL(new RegExp(`/m/${SEED.slug}/member/orders/\\d+`));
  });

  const member = await memberApi(request);
  type Order = { id: number; status: string; total: string; hold_expires_at: string | null; payment_status?: string; event_id?: number; seats?: unknown };
  const orders = rowsOf(await member.get<Order[] | { results: Order[] }>(`/member/makerspaces/${SEED.makerspaceId}/orders/`));
  expect(orders.length, "the free order is listed for the member").toBeGreaterThan(0);

  await test.step("a paid seat is held with an expiry until it is paid at the desk", async () => {
    const lines = { tickets: [{ ticket_type_id: paid.id, quantity: 1 }], buyer_attends: false };
    const quote = await member.post<{ digest: string; total: string }>(
      `/member/makerspaces/${SEED.makerspaceId}/events/${event.id}/orders/quote/`, lines);
    expect(Number(quote.total)).toBeGreaterThan(0);
    const placed = await member.post<{ order: Order; checkout_url: string }>(
      `/member/makerspaces/${SEED.makerspaceId}/events/${event.id}/orders/`, { ...lines, digest: quote.digest });
    // No online rail here (payments.events off): the seat is held and the charge waits at the desk.
    expect(placed.checkout_url ?? "").toBe("");
    expect(placed.order.hold_expires_at, "events.seat_holds holds the seat").toBeTruthy();
    expect(new Date(placed.order.hold_expires_at!).getTime()).toBeGreaterThan(Date.now());

    await page.goto(`/m/${SEED.slug}/member/orders/${placed.order.id}`);
    await expect(page.getByText(paid.name).first()).toBeVisible();
  });
});
