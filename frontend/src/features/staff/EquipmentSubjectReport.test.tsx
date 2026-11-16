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

function view(kind: "event" | "booking", { id = 45, tenant = 17, maker = tenant,
  enabled = modules, grants = actions }: { id?: number; tenant?: number; maker?: number;
    enabled?: string[]; grants?: string[] } = {}) {
  return <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3,
    actions: grants, makerspace: { id: maker, enabled_modules: enabled } }}>
    <EquipmentSubjectReport tenant={tenant} kind={kind} id={id} />
  </StaffListContext.Provider>;
}

it.each(["event", "booking"] as const)("opens and exports only the exact %s subject", async kind => {
  api.staffRequest.mockResolvedValue({ rows: [["request_id", "status"], [42, "issued"]] });
  // Force an export error to verify the real invocation without creating a browser file.
  api.staffRequestBlob.mockRejectedValue(new Error("offline"));
  const client = new QueryClient();
  render(<QueryClientProvider client={client}>{view(kind)}</QueryClientProvider>);
  expect(api.staffRequest).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "View equipment report" }));
  const base = "/admin/makerspace/17";
  const query = `subject_kind=${kind}&subject_id=45`;
  expect(await screen.findByText("issued")).toBeInTheDocument();
  expect(api.staffRequest).toHaveBeenCalledWith(`${base}/analytics/${kind}-equipment?${query}`, expect.any(Object));
  fireEvent.click(screen.getByRole("button", { name: "Download equipment CSV" }));
  await waitFor(() => expect(api.staffRequestBlob).toHaveBeenCalledWith(`${base}/reports/${kind}-equipment/export?${query}&format=csv`));
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be downloaded");
});

it.each(["event", "booking"] as const)("hides %s reports without tenant, actions or either source", kind => {
  const client = new QueryClient();
  for (const options of [{ maker: 99 }, { grants: ["view_inventory"] }, { grants: ["view_audit"] },
    { enabled: modules.filter(module => module !== "reports") },
    { enabled: modules.filter(module => module !== (kind === "event" ? "events" : "bookings")) }]) {
    const result = render(<QueryClientProvider client={client}>{view(kind, options)}</QueryClientProvider>);
    expect(screen.queryByRole("button", { name: "View equipment report" })).toBeNull();
    result.unmount();
  }
  expect(api.staffRequest).not.toHaveBeenCalled();
  expect(api.staffRequestBlob).not.toHaveBeenCalled();
});

it("clears the open report when the selected booking changes", async () => {
  api.staffRequest.mockResolvedValue({ rows: [["request_id", "status"], [42, "issued"]] });
  const client = new QueryClient();
  const tree = (id: number) => <QueryClientProvider client={client}>{view("booking", { id })}</QueryClientProvider>;
  const result = render(tree(45));
  fireEvent.click(screen.getByRole("button", { name: "View equipment report" }));
  expect(await screen.findByText("issued")).toBeInTheDocument();
  result.rerender(tree(46));
  expect(screen.queryByText("issued")).toBeNull();
  expect(api.staffRequest).toHaveBeenCalledTimes(1);
});
