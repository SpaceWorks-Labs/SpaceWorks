import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

import { EquipmentSubjectReport } from "./EquipmentSubjectReport";
import { StaffListContext } from "./StaffListContext";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", () => api);

const actions = ["view_inventory", "view_audit"];
const modules = ["reports", "request_workflow", "events", "bookings"];
beforeEach(() => { vi.resetAllMocks(); });

function view(kind: "event" | "booking", { enabled = modules, grants = actions }:
  { enabled?: string[]; grants?: string[] } = {}) {
  return <QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3, actions: grants,
      makerspace: { id: 17, enabled_modules: enabled } }}>
      <EquipmentSubjectReport tenant={17} kind={kind} id={45} />
    </StaffListContext.Provider>
  </QueryClientProvider>;
}

it.each(["event", "booking"] as const)("opens and exports the exact %s loan timeline", async kind => {
  api.staffRequest.mockResolvedValue({ rows: [["occurred_at", "request_id", "milestone"],
    ["2026-11-01T10:00:00Z", 42, "closed_with_issue"]] });
  api.staffRequestBlob.mockRejectedValue(new Error("offline"));
  render(view(kind));
  expect(api.staffRequest).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "View loan timeline" }));
  expect(await screen.findByText("closed_with_issue")).toBeInTheDocument();
  const query = `subject_kind=${kind}&subject_id=45`;
  expect(api.staffRequest).toHaveBeenCalledTimes(1);
  expect(api.staffRequest).toHaveBeenCalledWith(
    `/admin/makerspace/17/analytics/${kind}-loan-timeline?${query}`, expect.any(Object));
  fireEvent.click(screen.getByRole("button", { name: "Download loan timeline CSV" }));
  await waitFor(() => expect(api.staffRequestBlob).toHaveBeenCalledWith(
    `/admin/makerspace/17/reports/${kind}-loan-timeline/export?${query}&format=csv`));
  expect(await screen.findByRole("alert")).toHaveTextContent("loan timeline could not be downloaded");
});

it.each(["event", "booking"] as const)("hides the %s loan timeline without loans, its module or actions", kind => {
  for (const options of [{ enabled: modules.filter(module => module !== "request_workflow") },
    { enabled: modules.filter(module => module !== (kind === "event" ? "events" : "bookings")) },
    { grants: ["view_inventory"] }, { grants: ["view_audit"] }]) {
    const result = render(view(kind, options));
    expect(screen.queryByRole("button", { name: "View loan timeline" })).toBeNull();
    result.unmount();
  }
  expect(api.staffRequest).not.toHaveBeenCalled();
});

it("surfaces the timeline beside the equipment metrics", () => {
  render(view("booking"));
  expect(screen.getByRole("button", { name: "View equipment report" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "View loan timeline" })).toBeInTheDocument();
});
