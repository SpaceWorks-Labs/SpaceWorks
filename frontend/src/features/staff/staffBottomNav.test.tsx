import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { BottomTabs } from "../../components/shell/BottomTabs";
import { getStaffAccess } from "./staffAccess";
import { sidebarSections } from "./sidebarSections";
import { staffBottomNav } from "./staffBottomNav";

const SM = ["accept_request", "edit_inventory", "issue_request", "manage_bookings", "manage_events", "manage_machines", "manage_makerspace",
  "manage_members", "reject_request", "view_audit", "view_finance", "view_inventory"];

describe("decision 242 / U12: phone bottom bar for the Space Manager and the superadmin", () => {
  it("picks Home, Schedule, Requests and Inbox for the Space Manager", () => {
    const nav = sidebarSections(getStaffAccess(SM, false, false).allowedTabs, "dashboard", undefined, undefined, false, true);
    expect(staffBottomNav(nav, "space")?.map(item => item.key)).toEqual(["dashboard", "schedule", "requests", "notifications"]);
  });

  it("picks the platform pages before a space is chosen, and nothing for other roles", () => {
    const nav = sidebarSections(getStaffAccess([], true, false).allowedTabs, "platform-dashboard");
    expect(staffBottomNav(nav, "platform")?.map(item => item.key)).toEqual(["platform-dashboard", "platform-spaces", "platform-inbox", "platform-analytics"]);
    expect(staffBottomNav(nav, null)).toBeUndefined();
  });

  it("always offers More after a picked list", () => {
    const more = vi.fn();
    const nav = sidebarSections(getStaffAccess(SM, false, false).allowedTabs, "dashboard", undefined, undefined, false, true);
    render(<MemoryRouter><BottomTabs label="Staff quick navigation" items={staffBottomNav(nav, "space")!} activeKey="dashboard" onMore={more} more /></MemoryRouter>);
    expect(screen.getAllByRole("link")).toHaveLength(4);
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    expect(more).toHaveBeenCalled();
  });
});
