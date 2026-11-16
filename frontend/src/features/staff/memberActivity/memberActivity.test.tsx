import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { filterStaffRows, groupStaffRows, StaffRoleFilterBar } from "../panels/staffRoles/staffRoleFilters";
import type { StaffRoleRow } from "../panels/staffRoles/staffRolesApi";
import { MemberActivityDrawer } from "./MemberActivityDrawer";
import { MemberActivitySection } from "./MemberActivitySection";
import { ROSTER_FILTER_DEFAULTS, RosterFilters, rosterFilterQuery } from "./RosterFilters";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function wrap(node: ReactNode, tabs: string[], path = "/m/lab/admin/members") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AllowedTabsContext.Provider value={tabs}>{node}</AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}
const activity = {
  member_id: 21, errors: ["machines"],
  areas: [
    { area: "lending", count: 3, rows_visible: true, open: 1, rows: [{ id: 30, label: "Request #30", status: "issued", at: "2026-11-01T10:00:00Z", link: { tab: "requests", filters: { id: "30", history: "true" } } }] },
    { area: "bookings", count: 2, rows_visible: false, rows: null },
    { area: "money", count: 1, rows_visible: false, rows: null, pending: 1, owed: { INR: "250.00" } },
    { area: "shop", count: 4, rows_visible: true, rows: [{ id: 5, label: "Order #5", status: "paid", at: null, link: { tab: "shop", filters: { order: "5" } } }] },
  ],
};
const staff = (id: number, roles: string[]): StaffRoleRow => ({ id, user_id: id, username: `u${id}`, display_name: `Person ${id}`, email: "", roles,
  machine_type_ids: [], status: "active", mfa_enabled: false, granted_at: "", revoked_at: null, revocation_reason: "",
  can: { change_roles: false, revoke: false, restore: false, reset_mfa: false } });

describe("member 360 (PE1)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("shows counts for every area and rows only where the server sent them", async () => {
    api.staffRequest.mockResolvedValue(activity);
    wrap(<MemberActivitySection makerspaceId={4} userId={21} />, ["requests", "shop"]);
    expect(await screen.findByRole("heading", { name: /Inventory/ })).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/members/21/activity", expect.anything());
    expect(screen.getByRole("link", { name: /Request #30/ })).toHaveAttribute("href", "/m/lab/admin/requests?id=30&history=true");
    expect(screen.getByRole("link", { name: /Order #5/ })).toHaveAttribute("href", "/m/lab/admin/shop/orders?order=5");
    expect(screen.getByRole("link", { name: "Open Shop orders" })).toHaveAttribute("href", "/m/lab/admin/shop/orders?buyer=21");
    const bookings = screen.getByRole("heading", { name: /Bookings/ }).closest("li")!;
    expect(within(bookings).getByText("Counts only: this area is managed by someone else.")).toBeInTheDocument();
    expect(within(bookings).queryByRole("link")).toBeNull();
    expect(screen.getByText(/250/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Machine jobs and sessions");
  });

  it("disappears for a viewer the server refuses", async () => {
    api.staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(403, { detail: "no" })));
    const { container } = wrap(<MemberActivitySection makerspaceId={4} userId={21} />, []);
    await vi.waitFor(() => expect(api.staffRequest).toHaveBeenCalled());
    await vi.waitFor(() => expect(container.textContent).toBe(""));
  });

  it("opens from a cross-link with ?member=", async () => {
    api.staffRequest.mockResolvedValue({ member_id: 21, errors: [], areas: [] });
    wrap(<MemberActivityDrawer makerspaceId={4} />, [], "/m/lab/admin/members?member=21");
    expect(await screen.findByText("No activity in this space yet.")).toBeInTheDocument();
  });
});

describe("roster and staff filters (PE3, PE4)", () => {
  it("sends the roster filters in the server's names", () => {
    expect(rosterFilterQuery({ ...ROSTER_FILTER_DEFAULTS, status: "active", role: "3", access: "restricted", joined_after: "2026-01-01", minor: "true", waiver_needed: "true" }).toString())
      .toBe("status=active&role=3&standing=restricted&joined_after=2026-01-01&minor=true&waiver_needed=true");
    const onChange = vi.fn();
    render(<RosterFilters values={ROSTER_FILTER_DEFAULTS}
      roles={[{ id: 3, name: "Event Manager" } as never]} onChange={onChange} />);
    fireEvent.change(screen.getByRole("combobox", { name: "Role" }), { target: { value: "3" } });
    expect(onChange).toHaveBeenCalledWith("role", "3");
  });

  it("filters staff by role and groups them by the area their roles run", () => {
    const rows = [staff(1, ["space_manager"]), staff(2, ["machine_manager", "event_manager"]), staff(3, ["custom_desk"])];
    expect(filterStaffRows(rows, "event_manager").map(row => row.id)).toEqual([2]);
    expect(groupStaffRows(rows).map(group => [group.label, group.rows.map(row => row.id)]))
      .toEqual([["Whole space", [1]], ["Machines", [2]], ["Events", [2]], ["Other roles", [3]]]);
    const onChange = vi.fn();
    render(<StaffRoleFilterBar rows={rows} value={{ role: "", grouped: false }} onChange={onChange} partial />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Group by area" }));
    expect(onChange).toHaveBeenCalledWith({ role: "", grouped: true });
  });
});
