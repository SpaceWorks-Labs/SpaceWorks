import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError, tenantMemberRequest, tenantPublicRequest } from "../../lib/api";
import { PublicBookingForm } from "../bookings/PublicBookingForm";
import type { PublicBookableSpace } from "../bookings/publicBookingsApi";
import { EventRegistrationForm } from "../inventory/EventRegistrationForm";
import { isPriceChanged, PriceChangedNotice } from "./PriceChangedNotice";

vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), tenantPublicRequest: vi.fn(), tenantMemberRequest: vi.fn() }));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
// PublicBookingForm also builds its payments link with tenantPath + useOptionalTenant.
vi.mock("../../lib/tenant", () => {
  const tenant = { mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } };
  return { useTenantPath: () => (path: string) => `/m/lab/${path}`, useTenant: () => tenant, useOptionalTenant: () => tenant,
    tenantPath: (_mode: string, _slug: string, subpath = "") => `/${subpath}` };
});

const request = vi.mocked(tenantPublicRequest);
const memberRequest = vi.mocked(tenantMemberRequest);
const preview = (digest: string, total: string) => ({
  quote: { domain: "bookings", currency: "usd", mode: "paid", lines: [{ component: "per_booking", label: "Per booking", subject_type: "booking",
    quantity: "1.0000", unit_amount: total, gross: total, discount: "0.00", net: total, source: "default", cap_applied: false, target: null, detail: {} }],
  subtotal: total, discount_total: "0.00", total, discount: null, waiver: null, notes: [], digest },
  digest, tax: { net: total, tax: "0.00", gross: total, inclusive: false, mode: "none" },
  members_total: null, member_price_applied: false, deposit: null, policy: null, refund_summary: null,
});
// DRF error details stringify nested non-strings: null arrives as "None", booleans as "False".
const priceChanged = () => new StructuredApiError(409, { detail: "The price changed since you saw it.", code: "price_changed", quote: {
  domain: "bookings", currency: "usd", mode: "paid", total: "25.00", discount: "None", waiver: "None",
  lines: [{ label: "Per booking", net: "25.00", cap_applied: "False" }] } });

const space: PublicBookableSpace = { public_token: "room-1", name: "Room", kind: "meeting", description: "", capacity: 4, location: "",
  image_url: "", approval_mode: "instant", custom_form: null as never, show_public_availability: false, show_public_booker_names: false };

function show(node: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{node}</MemoryRouter></QueryClientProvider>);
}

const bodyOf = (path: string) => JSON.parse(String(memberRequest.mock.calls.filter(call => call[1].endsWith(path)).at(-1)?.[2]?.body));

describe("price digest at submit", () => {
  beforeEach(() => { request.mockReset(); memberRequest.mockReset(); });

  it("recognises only a 409 price_changed", () => {
    expect(isPriceChanged(priceChanged())).toBe(true);
    expect(isPriceChanged(new StructuredApiError(409, { code: "registration_closed" }))).toBe(false);
    expect(isPriceChanged(undefined)).toBe(false);
  });

  it("shows the new price from a stringified 409 body", () => {
    show(<PriceChangedNotice makerspaceSlug="lab" error={priceChanged()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The price changed — please check and confirm again.");
    expect(screen.getByText("New total").parentElement).toHaveTextContent("$25.00");
  });

  it("sends the booking preview's digest and lets the member resubmit after a price change", async () => {
    let digest = "d1";
    request.mockImplementation(async (_slug: string, path: string) => {
      if (path.endsWith("/pricing/quote")) return preview(digest, digest === "d1" ? "20.00" : "25.00");
      throw new Error(`Unexpected anonymous transport: ${path}`);
    });
    memberRequest.mockImplementation(async (_slug: string, path: string) => {
      if (path.endsWith("/book/") && digest === "d1") { digest = "d2"; throw priceChanged(); }
      return { status: "confirmed" };
    });
    show(<PublicBookingForm makerspaceSlug="lab" space={space} showCalendar={false} />);
    fireEvent.change(screen.getByLabelText("Starts"), { target: { value: "2099-01-01T10:00" } });
    fireEvent.change(screen.getByLabelText("Ends"), { target: { value: "2099-01-01T11:00" } });
    expect(await screen.findByText("Per booking")).toBeVisible();
    const quoteBody = JSON.parse(String(request.mock.calls.find(call => call[1].endsWith("/pricing/quote"))?.[2]?.body));
    expect(quoteBody).toMatchObject({ domain: "bookings", space_token: "room-1" });
    fireEvent.click(screen.getByRole("button", { name: "Book this slot" }));
    expect(await screen.findByText("The price changed — please check and confirm again.")).toBeVisible();
    expect(bodyOf("/book/").quote_digest).toBe("d1");
    await waitFor(() => expect(screen.getAllByText("$25.00").length).toBeGreaterThan(1));
    fireEvent.click(screen.getByRole("button", { name: "Book this slot" }));
    await screen.findByText("Space booked");
    expect(bodyOf("/book/").quote_digest).toBe("d2");
    expect(memberRequest.mock.calls.every(call => call[0] === "lab" && call[1].endsWith("/book/"))).toBe(true);
  });

  it("sends the event preview's digest with the registration", async () => {
    request.mockImplementation(async (_slug: string, path: string) =>
      path.endsWith("/pricing/quote") ? preview("e1", "10.00") : { status: "registered" });
    memberRequest.mockResolvedValue({ status: "registered" });
    show(<EventRegistrationForm makerspaceSlug="lab" publicToken="evt-1" waitlist={false} approvalRequired={false} customForm={null as never} />);
    expect(await screen.findByText("Per booking")).toBeVisible();
    expect(JSON.parse(String(request.mock.calls[0][2]?.body))).toMatchObject({ domain: "events", event_token: "evt-1" });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    await screen.findByText("Registration received");
    expect(bodyOf("/register/").quote_digest).toBe("e1");
    expect(memberRequest.mock.calls[0][0]).toBe("lab");
    expect(request.mock.calls.every(call => call[1].endsWith("/pricing/quote"))).toBe(true);
  });
});
