import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

import { EventEquipmentDesk } from "./EventEquipmentDesk";
import { StaffListContext } from "./StaffListContext";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => api);
vi.mock("./handover/HandoverWizard", () => ({
  HandoverWizard: ({ row, mode }: { row: { id: number }; mode: string }) => <div role="dialog">{`${mode} #${row.id}`}</div>,
}));
vi.mock("./loanRepairs/LoanRepairsPanel", () => ({ LoanRepairsPanel: ({ loan }: { loan: { id: number } }) => <p>{`repairs #${loan.id}`}</p> }));

const item = (overrides = {}) => ({ id: 1, product_id: 2, product_name: "Soldering iron", storage_location: "", tracking_mode: "quantity", requires_asset_qr: false,
  requested_quantity: 2, accepted_quantity: 2, issued_quantity: 0, returned_quantity: 0, damaged_quantity: 0, missing_quantity: 0, needs_fix_quantity: 0, ...overrides });
const row = (id: number, status: string, extra = {}) => ({ id, status, requester_username: `user${id}`, requester_display: `Person ${id}`, requested_for: "Workshop",
  return_due_at: null, return_reminder_sent_at: null, items: [item()], ...extra });
const desk = {
  summary: { awaiting_review: 1, ready_to_issue: 1, out: 1, overdue: 1, outstanding_units: 2, closed_with_issue: 1, event_ends_at: "2020-01-01T10:00:00Z" },
  ready: [row(10, "accepted")],
  out: [row(11, "issued", { return_due_at: "2020-01-01T10:00:00Z", items: [item({ issued_quantity: 2 })] })],
  closed: [row(12, "closed_with_issue", { items: [item({ issued_quantity: 2, returned_quantity: 1, damaged_quantity: 1 })] }), row(13, "returned")],
};

const allModules = ["events", "request_workflow", "staff_admin"];
function view({ modules = allModules, features = ["loans.enabled"], actions = ["issue_request"] } = {}) {
  return render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3, actions,
      makerspace: { id: 17, enabled_modules: modules, enabled_features: features } }}>
      <EventEquipmentDesk makerspaceId={17} eventId={45} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

beforeEach(() => { vi.resetAllMocks(); });

it("shows the event queue and opens the normal issue and return wizards", async () => {
  api.staffRequest.mockResolvedValue(desk);
  view();
  expect(await screen.findByRole("heading", { name: "Event equipment" })).toBeTruthy();
  expect(api.staffRequest.mock.calls[0][0]).toBe("/admin/makerspace/17/events/45/equipment-desk");
  expect(screen.getByText("1 awaiting review")).toBeTruthy();
  expect(screen.getByText("Still out after the event")).toBeTruthy();
  expect(screen.getAllByText("Overdue").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: /Issue/ }));
  expect(screen.getByRole("dialog").textContent).toBe("issue #10");
  fireEvent.click(screen.getByRole("button", { name: /Return/ }));
  expect(screen.getByRole("dialog").textContent).toBe("return #11");
  // Only damaged/missing closed loans are handed to repairs.
  expect(screen.getByText("repairs #12")).toBeTruthy();
  expect(screen.queryByText("repairs #13")).toBeNull();
});

it.each([
  { modules: ["request_workflow"] },
  { modules: ["events"] },
  { features: [] },
  { actions: ["view_inventory"] },
])("is absent without its module, feature or issue authority %#", options => {
  const { container } = view(options);
  expect(container.textContent).toBe("");
  expect(api.staffRequest).not.toHaveBeenCalled();
});

it("hides itself when the server refuses the desk", async () => {
  api.staffRequest.mockRejectedValue(Object.assign(new Error("Not found"), { status: 404 }));
  const { container } = view();
  await vi.waitFor(() => expect(api.staffRequest).toHaveBeenCalled());
  await vi.waitFor(() => expect(container.textContent).toBe(""));
});
