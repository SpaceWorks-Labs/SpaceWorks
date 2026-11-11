import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";

import { EventEquipmentDesk } from "./EventEquipmentDesk";
import { StaffListContext } from "./StaffListContext";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => api);
vi.mock("./handover/HandoverWizard", () => ({ HandoverWizard: () => null }));
vi.mock("./loanRepairs/LoanRepairsPanel", () => ({ LoanRepairsPanel: () => null }));

const item = { id: 1, product_id: 2, product_name: "Soldering iron", storage_location: "", tracking_mode: "quantity", requires_asset_qr: false,
  requested_quantity: 2, accepted_quantity: 2, issued_quantity: 0, returned_quantity: 0, damaged_quantity: 0, missing_quantity: 0, needs_fix_quantity: 0 };
const ready = { id: 10, status: "accepted", requester_username: "user10", requester_display: "Person 10", requested_for: "Workshop",
  return_due_at: null, return_reminder_sent_at: null, items: [item] };

it("lists equipment warnings for the event's loans without changing the queue", async () => {
  api.staffRequest.mockResolvedValue({
    summary: { awaiting_review: 0, ready_to_issue: 1, out: 0, overdue: 0, outstanding_units: 0, closed_with_issue: 0, event_ends_at: null,
      equipment_warnings: [{ product_id: 2, product_name: "Soldering iron", code: "units_under_repair", count: 2 },
        { product_id: 3, product_name: "Oscilloscope", code: "insufficient_stock", count: 4 }] },
    ready: [ready], out: [], closed: [],
  });
  render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3, actions: ["issue_request"],
      makerspace: { id: 17, enabled_modules: ["events", "request_workflow", "staff_admin"], enabled_features: ["loans.enabled"] } }}>
      <EventEquipmentDesk makerspaceId={17} eventId={45} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
  const list = await screen.findByRole("list", { name: "Equipment warnings" });
  expect(list).toHaveTextContent("Soldering iron: 2 under repair or waiting to be fixed.");
  expect(list).toHaveTextContent("Oscilloscope: requests awaiting review ask for 4, more than is available now.");
  expect(screen.getByRole("button", { name: /Issue/ })).toBeVisible();
});
