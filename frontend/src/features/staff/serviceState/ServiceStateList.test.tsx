import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getStaffAccess } from "../staffAccess";
import { AccountabilityPanel } from "../panels/AccountabilityPanel";
import type { Makerspace } from "../panels/shared";
import { ServiceStateList } from "./ServiceStateList";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function wrap(node: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/admin/repairs"]}>{node}</MemoryRouter></QueryClientProvider>);
}
const rows = [
  { subject_type: "machine", subject_id: 12, name: "Laser A", machine_type: "Laser", status: "idle", in_service: true },
  { subject_type: "machine", subject_id: 13, name: "Lathe", machine_type: "Lathe", status: "maintenance", in_service: false },
];

describe("service state (MC6)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("takes a covered machine out of service with a reason, without a repair job", async () => {
    api.staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST"
      ? { state: "out_of_service", outage_id: null, affected_bookings: [] } : rows));
    wrap(<ServiceStateList makerspaceId={4} />);
    fireEvent.click(await screen.findByRole("button", { name: "Take out of service" }));
    const submit = screen.getAllByRole("button", { name: "Take out of service" }).at(-1)!;
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Why is Laser A out of service?" }), { target: { value: "Mirror cracked" } });
    fireEvent.click(submit);
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/service-state", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(api.staffRequest.mock.calls.find(([, init]) => init?.method === "POST")![1].body);
    expect(body).toEqual({ subject_type: "machine", subject_id: 12, in_service: false, reason: "Mirror cracked" });
  });

  it("brings a machine back in service in one click", async () => {
    api.staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? { state: "in_service", outage_id: null, affected_bookings: [] } : rows));
    wrap(<ServiceStateList makerspaceId={4} />);
    fireEvent.click(await screen.findByRole("button", { name: "Back in service" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/service-state",
      expect.objectContaining({ body: JSON.stringify({ subject_type: "machine", subject_id: 13, in_service: true }) })));
  });
});

describe("accountability for the Inventory Manager (IN8)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("opens the tab for view_inventory but not for a handout-only desk", () => {
    expect(getStaffAccess(["view_inventory", "edit_inventory", "accept_request"], false, false).allowedTabs).toContain("accountability");
    expect(getStaffAccess(["view_inventory", "issue_request"], false, false).allowedTabs).not.toContain("accountability");
  });

  it("shows overdue and repeat damage only, with no restriction tools", async () => {
    api.staffRequest.mockResolvedValue({ overdue: [], problem_reports: [], repeat_offenders: [{ requester_id: 3, username: "asha", damaged: 2, missing: 0, total_issues: 2, total_quantity: 2, access_status: "active" }],
      restrictions: [], anonymous_accountability: null, truncated: { overdue: false, problem_reports: false, repeat_offenders: false } });
    wrap(<AccountabilityPanel makerspace={{ id: 4, slug: "lab", name: "Lab" } as Makerspace} isSuperadmin={false} inventoryView />);
    expect(await screen.findByText("asha")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Problems/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Restricted/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Restrict/ })).toBeNull();
  });
});
