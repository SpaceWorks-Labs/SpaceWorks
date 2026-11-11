import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

import { EventLinkedFinancePanel } from "./EventLinkedFinancePanel";
import { StaffListContext } from "./StaffListContext";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), staffRequest: api.staffRequest }));

beforeEach(() => { vi.resetAllMocks(); });

const charges = (currency: string, owed: string, extra = {}) => ({ currency, charges: 1, owed, paid_online: "0.00",
  paid_offline: "0.00", offline_receipts: 0, offline_by_method: {}, waived: "0.00", refunded: "0.00", ...extra });

function view({ tenant = 17, maker = tenant, enabled = ["events", "bookings"] }: { tenant?: number; maker?: number; enabled?: string[] } = {}) {
  return <QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3,
      makerspace: { id: maker, enabled_modules: enabled } }}>
      <EventLinkedFinancePanel tenant={tenant} eventId={45} />
    </StaffListContext.Provider>
  </QueryClientProvider>;
}

it("shows each owner side by side with currencies kept apart and the room charge Booking-owned", async () => {
  api.staffRequest.mockResolvedValue({ event_id: 45, sections: {
    registration_charges: { owner: "events", source: "payments.Payment", tracking_enabled: true, currencies: [
      charges("inr", "10.00", { paid_offline: "20.00", offline_receipts: 1, offline_by_method: { cash: "20.00" } }),
      charges("usd", "0.00", { paid_online: "5.00" })] },
    booking_room_charge: { owner: "bookings", label: "Booking-owned", read_only: true, source: "bookings.Booking",
      state: "linked", booking_ids: [9], currencies: [charges("inr", "40.00")] },
  } });
  render(view());
  expect(api.staffRequest).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "View linked finance" }));
  expect(await screen.findByText("Registration charges")).toBeInTheDocument();
  expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/17/finance/events/45/linked", expect.any(Object));
  expect(screen.getByText("Booking-owned")).toBeInTheDocument();
  expect(screen.getByText(/Read only\. Bookings 9/)).toBeInTheDocument();
  expect(screen.getByText("Paid offline (1 receipt)")).toBeInTheDocument();
  // One group per currency; nothing adds INR to USD or the room charge to registrations.
  expect(screen.getAllByRole("definition").length).toBeGreaterThan(0);
  expect(screen.getAllByLabelText("INR")).toHaveLength(2);
  expect(screen.getAllByLabelText("USD")).toHaveLength(1);
  const room = screen.getByText("Booking room charge").closest("article") as HTMLElement;
  expect(within(room).queryByLabelText("USD")).toBeNull();
  for (const hidden of ["Reimbursements", "Payouts", "Budget against actual", "Venue fee"]) {
    expect(screen.queryByText(hidden)).toBeNull();
  }
});

it("reports an unavailable view without inventing sections", async () => {
  api.staffRequest.mockRejectedValue(new Error("404"));
  render(view());
  fireEvent.click(screen.getByRole("button", { name: "View linked finance" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("unavailable for your access");
  expect(screen.queryByText("Registration charges")).toBeNull();
});

it("hides the panel for another tenant or with Events off", () => {
  for (const options of [{ maker: 99 }, { enabled: ["bookings"] }]) {
    const result = render(view(options));
    expect(screen.queryByRole("button", { name: "View linked finance" })).toBeNull();
    result.unmount();
  }
  expect(api.staffRequest).not.toHaveBeenCalled();
});
