import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { defaults, queryClient, renderWorkspace, resetShellMocks, user, wrap } from "../../../../e2e/fixtures/staffShellHarness";
import { getStaffAccess } from "../staffAccess";
import { StaffApp } from "../StaffApp";
import { staffTabPath } from "../staffTabs";

const { session } = vi.hoisted(() => ({ session: vi.fn() }));
vi.mock("../useConsoleSession", () => ({ useConsoleSession: session }));

const PAGES = ["platform-inbox", "platform-access", "platform-security", "platform-data", "platform-limits", "platform", "platform-analytics"];
const platformUser = () => user({ is_superuser: true, role: "superadmin", kind: "platform", makerspaces: [] });

beforeEach(() => { setRouteSessionContext("platform"); resetShellMocks(); });

describe("the platform console before a space is chosen (0.12.0)", () => {
  it("lists every platform page in two sections", () => {
    renderWorkspace("/admin/platform-data", { isSuperadmin: true, actions: [], activeMakerspace: undefined, selected: null, user: platformUser() });
    expect(screen.getByTestId("tab")).toHaveTextContent("platform-data");
    const nav = within(screen.getByRole("navigation", { name: "Staff sections" }));
    for (const name of ["Platform dashboard", "Spaces", "Inbox across spaces", "Platform analytics", "People & roles", "Limits & hosting", "Security & audit", "Data & recovery", "Platform settings"]) {
      expect(nav.getByRole("link", { name })).toHaveAttribute("href", expect.stringContaining("context=platform"));
    }
    expect(nav.queryByRole("link", { name: "Inventory" })).toBeNull();
  });

  it.each(PAGES)("opens /admin/%s without the space picker", tab => {
    const props = defaults();
    session.mockReturnValue({ ...props, user: user({ is_superuser: true }), restoring: false, recovery: { data: null },
      makerspaces: { data: props.makerspaces, isLoading: false }, consoleMakerspaces: props.makerspaces, selected: null,
      activeMakerspace: undefined, tenant: { bootstrap: { makerspace: { name: "Community Lab" } } }, queryClient: queryClient(),
      setUser: vi.fn(), chooseMakerspace: vi.fn(), login: { mutate: vi.fn() } });
    wrap(<StaffApp />, staffTabPath(tab, false));
    expect(screen.getByTestId("tab")).toHaveTextContent(tab);
    expect(screen.queryByText("Choose a makerspace to operate")).toBeNull();
  });

  it("keeps the pages for the superadmin on a multi-space deployment only", () => {
    for (const tab of PAGES) {
      expect(getStaffAccess([], true, false).allowedTabs).toContain(tab);
      expect(getStaffAccess(["manage_makerspace"], true, false).allowedTabs).toContain(tab);
      expect(getStaffAccess([], true, true).allowedTabs).not.toContain(tab);
      expect(getStaffAccess(["manage_makerspace", "view_audit"], false, false).allowedTabs).not.toContain(tab);
    }
  });

  it("routes every platform page without a space slug", () => {
    for (const tab of PAGES) expect(staffTabPath(tab, false, "north-lab")).toBe(`/admin/${tab}`);
  });
});
