import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

import { EventEquipmentDesk } from "./EventEquipmentDesk";
import { StaffListContext } from "./StaffListContext";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest }));

const idle = { summary: { awaiting_review: 0, ready_to_issue: 0, out: 0, overdue: 0, outstanding_units: 0, closed_with_issue: 0,
  event_ends_at: null, equipment_return_hours: 12 }, ready: [], out: [], closed: [] };

function view(canEditWindow: boolean) {
  return render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 3, actions: ["issue_request"],
      makerspace: { id: 17, enabled_modules: ["events", "request_workflow", "staff_admin"], enabled_features: ["loans.enabled"] } }}>
      <EventEquipmentDesk makerspaceId={17} eventId={45} canEditWindow={canEditWindow} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue(idle); });

it("shows the return window to an event editor even before any loan exists", async () => {
  view(true);
  expect(await screen.findByLabelText(/Items due N hours after the event ends/)).toHaveValue(12);
});

it("stays out of the way for a desk with nothing to do when the viewer cannot edit", async () => {
  const { container } = view(false);
  await waitFor(() => expect(container).toBeEmptyDOMElement());
  expect(staffRequest).toHaveBeenCalled();
});
