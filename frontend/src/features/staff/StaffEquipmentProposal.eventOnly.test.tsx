import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api/errors";
import { PendingIntake, type StaffBody } from "../inventory/contextualIntake";
import { StaffEquipmentProposal } from "./StaffEquipmentProposal";
import { StaffListContext } from "./StaffListContext";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: mock.request, memberRequest: vi.fn() }));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionOwner: () => "1" }));

it("badges an event-only item and treats a booking's event_only_product refusal as definite", async () => {
  mock.request.mockImplementation((path: string) => {
    if (path.includes("equipment-request-products")) return Promise.resolve({ results: [{ id: 8, name: "Oscilloscope", event_only: true }], next: null, previous: null });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    return Promise.reject(new StructuredApiError(409, { code: "event_only_product", detail: "x", products: ["Oscilloscope"] }));
  });
  const owner = new PendingIntake<StaffBody>();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["bookings", "staff_admin"], enabled_features: ["loans.enabled"] } }}>
      <StaffEquipmentProposal tenant={4} domain="booking" resourceId={9} targetId={3} pendingOwner={owner} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: /Oscilloscope/ }));
  expect(screen.getByText("Events only")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  expect(await screen.findByText(/lent only through an event: Oscilloscope/)).toBeInTheDocument();
  // Not an unknown outcome: no "Retry the same request" for a definite refusal.
  expect(screen.queryByRole("button", { name: "Retry the same request" })).toBeNull();
});
