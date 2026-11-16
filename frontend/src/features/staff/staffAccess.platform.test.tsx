import { beforeEach, describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { getStaffAccess } from "./staffAccess";
import { renderWorkspace, resetShellMocks, mocks, user } from "../../../e2e/fixtures/staffShellHarness";

beforeEach(() => { setRouteSessionContext("platform"); resetShellMocks(); });

const SUPERADMIN = ["accept_request", "assign_box", "collect_service_request", "edit_inventory", "issue_direct_loan", "issue_request",
  "manage_bookings", "manage_devices", "manage_events", "manage_machines", "manage_makerspace", "manage_member_cards", "manage_members",
  "manage_printing", "manage_qr", "record_payment", "record_reimbursement_payout", "reject_request", "return_request", "scan_member_cards",
  "upload_evidence", "view_audit", "view_finance", "view_inventory"];

describe("platform workspace before a space is chosen", () => {
  it("offers only platform operations and defaults to the platform dashboard", () => {
    const access = getStaffAccess([], true, false);
    // Spaces (c83723fb) and Analytics (7623e0da, L25) are platform tabs too.
    // People & access, Platform security and Data & recovery joined them in 0.12.0.
    expect(access.allowedTabs).toEqual(["platform-dashboard", "platform-spaces", "platform-inbox", "platform-access", "platform-security", "platform-data",
      "platform-limits", "users", "security", "organizations", "modules", "backups", "migration", "platform", "platform-analytics"]);
    expect(access.defaultTab).toBe("platform-dashboard");
    expect(access.canEditInventory).toBe(false);
    expect(access.canViewFinance).toBe(false);
  });

  it("uses staff lifecycle as its supported single-tenant landing", () => {
    const access = getStaffAccess([], true, true);
    expect(access.defaultTab).toBe("users");
    expect(access.allowedTabs).toEqual(["users", "security", "modules", "backups", "migration"]);
  });

  it.each(["/admin", "/admin/dashboard"])("normalizes %s without mounting tenant operations", path => {
    renderWorkspace(path, { isSuperadmin: true, actions: [], activeMakerspace: undefined, selected: null,
      user: user({ is_superuser: true, role: "superadmin", kind: "platform", makerspaces: [] }) });
    expect(screen.getByTestId("location")).toHaveTextContent("/admin/platform-dashboard");
    expect(screen.getByTestId("tab")).toHaveTextContent("platform-dashboard");
    expect(mocks.content.mock.calls.every(([props]) => props.activeTab === "platform-dashboard")).toBe(true);
    const navigation = within(screen.getByRole("navigation", { name: "Staff sections" }));
    expect(navigation.queryByRole("link", { name: "Inventory" })).toBeNull();
    expect(navigation.queryByRole("link", { name: "Payments" })).toBeNull();
    expect(screen.queryByRole("button", { name: /search and commands/i })).toBeNull();
    expect(mocks.request.mock.calls.some(([url]) => /\/search|\/jobs|notification-inbox/.test(url))).toBe(false);
  });

  it("refuses a stale tenant bookmark before mounting its panel", () => {
    renderWorkspace("/admin/inventory", { isSuperadmin: true, actions: [], activeMakerspace: undefined, selected: null });
    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(mocks.content).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Go to Platform dashboard" })).toHaveAttribute("href", expect.stringContaining("/admin/platform-dashboard"));
  });
});

describe("platform workspace inside a chosen space (#115)", () => {
  it("holds every action and opens the space's tenant tabs next to the platform ones", () => {
    const access = getStaffAccess(SUPERADMIN, true, false);
    for (const tab of ["dashboard", "requests", "inventory", "reports", "ledger", "settings", "emailtemplates", "email-logs",
      "exports", "members", "payments", "audit", "platform-dashboard", "platform", "modules"]) expect(access.allowedTabs).toContain(tab);
    expect(access.canSeeHardware).toBe(true);
    expect(access.canViewFinance).toBe(true);
    expect(access.handoutOnly).toBe(false);
    for (const tab of ["channels", "organized", "organization-analytics", "granted"]) expect(access.allowedTabs).not.toContain(tab);
  });

  it("mounts tenant panels with search for the chosen space", () => {
    renderWorkspace("/admin/reports", { isSuperadmin: true, actions: SUPERADMIN,
      user: user({ is_superuser: true, role: "superadmin", kind: "platform", makerspaces: [] }) });
    expect(screen.getByTestId("tab")).toHaveTextContent("reports");
    const navigation = within(screen.getByRole("navigation", { name: "Staff sections" }));
    expect(navigation.getByRole("link", { name: "Requests" })).toHaveAttribute("href", "/admin/requests?context=platform");
    expect(screen.getAllByRole("button", { name: /search and commands/i }).length).toBeGreaterThan(0);
    expect(screen.getByText("Working in Community Lab as the platform superadmin.")).toBeInTheDocument();
  });
});
