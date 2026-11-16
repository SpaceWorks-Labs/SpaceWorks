import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

import { EquipmentSubjectReport } from "./EquipmentSubjectReport";
import { StaffListContext } from "./StaffListContext";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", () => api);

const actions = ["view_inventory", "view_audit"];
const modules = ["reports", "events", "bookings"];
const features = ["inventory.consumables"];
beforeEach(() => { vi.resetAllMocks(); });

function view(kind: "event" | "booking", { enabled = modules, grants = actions, switches = features }:
  { enabled?: string[]; grants?: string[]; switches?: string[] } = {}) {
  return <QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3, actions: grants,
      makerspace: { id: 17, enabled_modules: enabled, enabled_features: switches } }}>
      <EquipmentSubjectReport tenant={17} kind={kind} id={45} />
    </StaffListContext.Provider>
  </QueryClientProvider>;
}

it.each(["event", "booking"] as const)("loads the %s consumables summary without the loan workflow", async kind => {
  api.staffRequest.mockResolvedValue({ rows: [["product_name", "used_quantity"], ["Solder wire", 4]] });
  render(view(kind));
  expect(screen.queryByRole("button", { name: "View equipment report" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "View consumables report" }));
  expect(await screen.findByText("Solder wire")).toBeInTheDocument();
  expect(api.staffRequest).toHaveBeenCalledWith(
    `/admin/makerspace/17/analytics/${kind}-consumables?subject_kind=${kind}&subject_id=45`, expect.any(Object));
});

it.each(["event", "booking"] as const)("hides the %s consumables summary without its switch, module or actions", kind => {
  for (const options of [{ switches: [] }, { grants: ["view_inventory"] }, { grants: ["view_audit"] },
    { enabled: modules.filter(module => module !== (kind === "event" ? "events" : "bookings")) }]) {
    const result = render(view(kind, options));
    expect(screen.queryByRole("button", { name: "View consumables report" })).toBeNull();
    result.unmount();
  }
  expect(api.staffRequest).not.toHaveBeenCalled();
});

it("shows both activity reports when loans and consumables are on", () => {
  render(view("event", { enabled: [...modules, "request_workflow"] }));
  expect(screen.getByRole("button", { name: "View equipment report" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "View consumables report" })).toBeInTheDocument();
});
