import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { TenantProvider } from "../../../lib/tenant";
import { TicketManageActions } from "./TicketManageActions";

const mocks = vi.hoisted(() => ({ member: vi.fn(), tenant: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.member, tenantPublicRequest: mocks.tenant }));

const shop = { event_id: 5, orders_enabled: true, currency: "inr", addons: [], booking_fee_fixed: "0", booking_fee_bps: 0,
  max_tickets_per_order: 4, promo_codes_enabled: false, policy: { text: "", overridden: false, terms: null },
  ticket_types: [
    { id: 1, name: "General", amount: "10.00", audience: "public", pricing_mode: "fixed", min_amount: "0", seats_per_ticket: 1,
      min_quantity: 1, per_order_limit: 4, spots_left: 5, sold_out: false, next_tier: null },
    { id: 2, name: "VIP", amount: "50.00", audience: "public", pricing_mode: "fixed", min_amount: "0", seats_per_ticket: 1,
      min_quantity: 1, per_order_limit: 4, spots_left: 0, sold_out: true, next_tier: null },
    { id: 3, name: "Supporter", amount: "30.00", audience: "public", pricing_mode: "fixed", min_amount: "0", seats_per_ticket: 1,
      min_quantity: 1, per_order_limit: 4, spots_left: 5, sold_out: false, next_tier: null },
  ] };
const future = new Date(Date.now() + 7 * 86400000).toISOString();

function show(props: Partial<Parameters<typeof TicketManageActions>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/events/31/ticket"]}><TenantProvider>
    <TicketManageActions makerspaceId={7} makerspaceSlug="lab" registrationId={31} status="registered"
      event={{ public_token: "tok", starts_at: future }} currentTicketTypeId={1} {...props} />
  </TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); mocks.tenant.mockResolvedValue(shop); });

describe("ticket transfer and type change", () => {
  it("offers the ticket to an email address and shows when the offer expires", async () => {
    mocks.member.mockResolvedValue({ id: 9, status: "offered", expires_at: "2026-12-01T10:00:00Z" });
    show();
    fireEvent.change(screen.getByLabelText("Their email address"), { target: { value: "friend@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send the transfer offer" }));
    await waitFor(() => expect(mocks.member).toHaveBeenCalledWith("/member/makerspaces/7/event-registrations/31/transfer/",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ email: "friend@example.com" }) })));
    expect(await screen.findByText(/Offer sent\. It expires/)).toBeVisible();
  });

  it("lists only other ticket types that are not sold out, and confirms a change", async () => {
    mocks.member.mockResolvedValue({ status: "changed", registration_id: 31, order: null, checkout_url: "" });
    show();
    const select = await screen.findByLabelText("New ticket type");
    const labels = Array.from((select as HTMLSelectElement).options).map(option => option.textContent ?? "");
    expect(labels.some(label => label.startsWith("Supporter"))).toBe(true);
    expect(labels.some(label => label.startsWith("General"))).toBe(false);
    expect(labels.some(label => label.startsWith("VIP"))).toBe(false);
    fireEvent.change(select, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Change my ticket" }));
    await waitFor(() => expect(mocks.member).toHaveBeenCalledWith("/member/makerspaces/7/event-registrations/31/change-type/",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ ticket_type_id: 3 }) })));
    expect(await screen.findByText("Your ticket type is changed.")).toBeVisible();
  });

  it("links to checkout and the order when the difference must be paid", async () => {
    mocks.member.mockResolvedValue({ status: "payment_required", registration_id: 31,
      order: { id: 44 }, checkout_url: "https://pay.example.com/c/1" });
    show();
    fireEvent.change(await screen.findByLabelText("New ticket type"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Change my ticket" }));
    expect(await screen.findByRole("link", { name: "Pay the difference" })).toHaveAttribute("href", "https://pay.example.com/c/1");
    expect(screen.getByRole("link", { name: "View the order" }).getAttribute("href")).toContain("member/orders/44");
  });

  it("never links a checkout address that is not a web address", async () => {
    mocks.member.mockResolvedValue({ status: "payment_required", registration_id: 31, order: { id: 44 }, checkout_url: "javascript:alert(1)" });
    show();
    fireEvent.change(await screen.findByLabelText("New ticket type"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Change my ticket" }));
    expect(await screen.findByRole("link", { name: "View the order" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Pay the difference" })).toBeNull();
  });

  it("shows the server's refusal", async () => {
    mocks.member.mockRejectedValue(new StructuredApiError(400, { detail: "This ticket cannot be transferred.", code: "transfer_refused" }));
    show();
    fireEvent.change(screen.getByLabelText("Their email address"), { target: { value: "friend@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send the transfer offer" }));
    expect(await screen.findByText("This ticket cannot be transferred.")).toBeVisible();
  });

  it("offers nothing for a past event or an unconfirmed place", () => {
    show({ status: "pending_approval" });
    expect(screen.queryByText("Transfer this ticket")).toBeNull();
  });
});
