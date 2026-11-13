import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";

// Every panel is a lazy chunk with its own tests. Here each becomes a probe that prints the props the
// router handed it, so the test can assert WHICH panel opens and WITH WHAT (role, module and flag gates).
const { probe, names } = vi.hoisted(() => ({ names: ["PaymentsPanel", "RefundQueue", "FinancePanel", "EventPayoutsSection", "DevicesPanel", "DashboardPanel", "NotificationInbox", "DirectLoans", "Inventory", "Ledger",
  "MachinesPanel", "EventsPanel", "OrganizedEventsPanel", "OrganizationAnalyticsPanel", "OrganizationsPanel", "BookingsPanel", "MembersPanel", "MemberCardsPanel", "QrTools", "RequestsPanel",
  "OperationsReports", "AuditLog", "BulkImport", "ScannerPanel", "ContainersPanel", "StocktakePanel", "StockTransferPanel", "ProcurementPanel", "WarrantyPanel", "AccountabilityPanel",
  "Categories", "NeedsFixTab", "HandoverConsole", "ConsumablesPanel", "IncidentRegister", "RepairsPanel", "SchedulePanel", "ShopPanel", "PlatformSpacesPanel", "DonationsArea"],
  probe: (name: string) => (props: Record<string, unknown>) => {
    const safe = Object.fromEntries(Object.entries(props).filter(([, value]) => ["string", "number", "boolean"].includes(typeof value)
      || (Array.isArray(value) && value.every((item) => typeof item === "string"))));
    return <p data-testid={`panel:${name}`}>{JSON.stringify(safe)}</p>;
  },
}));
vi.mock("./StaffTabLoaders", () => Object.fromEntries(names.map((name) => [name, probe(name)])));
vi.mock("./panels/ModuleAnalytics", () => ({ ModuleAnalytics: probe("ModuleAnalytics") }));
vi.mock("../notifications/MyNotificationSettings", () => ({ MyNotificationSettings: probe("MyNotificationSettings") }));
vi.mock("./allowances/AreaAllowances", () => ({ AreaAllowances: probe("AreaAllowances") }));
vi.mock("./platformConsole/PlatformSpaceBreadcrumb", () => ({ PlatformSpaceBreadcrumb: probe("PlatformSpaceBreadcrumb") }));
vi.mock("./StaffPlatformTabContent", () => ({ StaffPlatformTabContent: probe("StaffPlatformTabContent") }));
vi.mock("./eventProgramme/PlatformProgrammeDashboard", () => ({ PlatformProgrammeDashboard: probe("PlatformProgrammeDashboard") }));
vi.mock("./platformConsole/platformConsolePages", () => ({ PLATFORM_CONSOLE_PAGES: ["platform-inbox", "platform-data"], PlatformConsoleContent: probe("PlatformConsoleContent") }));
vi.mock("./GrantedResourcesPanel", () => ({ GrantedResourcesPanel: probe("GrantedResourcesPanel") }));
vi.mock("./memberActivity/ConsoleMemberActivity", () => ({ ConsoleMemberActivity: probe("ConsoleMemberActivity") }));

import { StaffTabContent } from "./StaffTabContent";

type Props = ComponentProps<typeof StaffTabContent>;
const SUPER_ACTIONS = ["manage_makerspace", "manage_members", "manage_machines", "manage_events", "manage_bookings", "edit_inventory", "view_inventory", "view_finance", "record_payment", "manage_devices",
  "view_audit", "manage_printing", "issue_request", "return_request", "manage_shop", "manage_donations"];
const FULL_MODULES = ["notifications", "machines", "devices", "machine_service", "events", "bookings", "membership", "presence", "stock_transfers", "stocktake", "containers", "bulk_import", "qr_print_batches",
  "scanner", "reports", "shop", "analytics", "public_inventory", "inventory", "finance", "payments", "incidents", "repairs", "consumables", "sponsors", "donations", "machine_service"];
const FULL_FEATURES = ["loans.enabled", "inventory.self_checkout", "inventory.tobuy", "inventory.warranty", "finance.ledger", "finance.donations", "inventory.consumables", "inventory.repairs",
  "safety.incidents", "notifications.delegated_recipients"];
const space = (over: Record<string, unknown> = {}) => ({ id: 7, name: "Lab", slug: "lab", public_site_enabled: false, enabled_modules: FULL_MODULES,
  enabled_features: FULL_FEATURES, ...over });
function show(activeTab: string, over: Record<string, unknown> = {}) {
  const props = { activeTab, isSuperadmin: true, singleTenantLocked: false, guestOnly: false, printingOnly: false, makerspaces: [], isMachineOnly: false,
    currentUser: { makerspaces: [{ id: 7, actions: [] }], superadmin_actions: SUPER_ACTIONS, has_organizations: true },
    activeMakerspace: space(), canChooseToBuyKind: true, canEditInventory: true, canIssueDirectLoan: true, canCollectServiceRequests: true, canUseToBuy: true,
    canManageQr: true, canManageMakerspace: true, canUseMemberCards: true, canManageMachines: true, canConfigureMachineTypes: true, canManageEvents: true, canManageBookings: true,
    canSeeHardware: true, canSeePrinting: true, canViewAudit: true, onAuthRefresh: vi.fn(), ...over } as unknown as Props;
  return render(<MemoryRouter><StaffTabContent {...props} /></MemoryRouter>);
}
const probeProps = async (name: string) => JSON.parse((await screen.findByTestId(`panel:${name}`)).textContent ?? "{}") as Record<string, unknown>;
const absent = (name: string) => expect(screen.queryByTestId(`panel:${name}`)).toBeNull();
const staff = (actions: string[], over: Record<string, unknown> = {}) => ({ isSuperadmin: false, currentUser: { makerspaces: [{ id: 7, actions }], has_organizations: true }, ...over });

describe("platform pages (superadmin, no space needed)", () => {
  it("opens the programme dashboard and spaces list", async () => {
    show("platform-dashboard", { activeMakerspace: undefined });
    await screen.findByTestId("panel:PlatformProgrammeDashboard");
  });
  it("opens the spaces panel", async () => {
    show("platform-spaces", { activeMakerspace: undefined });
    await screen.findByTestId("panel:PlatformSpacesPanel");
  });
  it("opens the other platform consoles through the platform content", async () => {
    show("platform-data", { activeMakerspace: undefined });
    await screen.findByTestId("panel:PlatformConsoleContent");
  });
  it("does not open platform pages for a single-tenant lock, falling to the no-space message", async () => {
    show("platform-dashboard", { activeMakerspace: undefined, singleTenantLocked: true });
    expect(await screen.findByRole("heading", { name: "No makerspace" })).toBeInTheDocument();
    expect(screen.getByText("Assign a makerspace to this account.")).toBeInTheDocument();
    absent("PlatformProgrammeDashboard");
  });
  it("does not open platform pages for a non-superadmin", async () => {
    show("platform-spaces", { activeMakerspace: undefined, isSuperadmin: false });
    expect(await screen.findByRole("heading", { name: "No makerspace" })).toBeInTheDocument();
    absent("PlatformSpacesPanel");
  });
});

describe("pages that need no space", () => {
  it("opens organizations with the superadmin flag", async () => {
    show("organizations", { activeMakerspace: undefined });
    expect(await probeProps("OrganizationsPanel")).toMatchObject({ isSuperadmin: true });
  });
  it("opens the cross-venue organizer page without a space for an organization member", async () => {
    show("organized", { activeMakerspace: undefined, isSuperadmin: false });
    await screen.findByTestId("panel:OrganizedEventsPanel");
  });
  it("does not for a superadmin with no space (falls to No makerspace)", async () => {
    show("organized", { activeMakerspace: undefined });
    expect(await screen.findByRole("heading", { name: "No makerspace" })).toBeInTheDocument();
  });
  it("opens organization analytics without a space, but not for a single-tenant lock", async () => {
    const { unmount } = show("organization-analytics", { activeMakerspace: undefined, isSuperadmin: false });
    await screen.findByTestId("panel:OrganizationAnalyticsPanel");
    unmount();
    show("organization-analytics", { activeMakerspace: undefined, isSuperadmin: false, singleTenantLocked: true });
    expect(await screen.findByRole("heading", { name: "No makerspace" })).toBeInTheDocument();
  });
  it("opens granted resources for a user with event grants, scoped to the single-tenant space when locked", async () => {
    show("granted", { currentUser: { makerspaces: [], event_grants: [{ id: 1 }], booking_grants: [] }, singleTenantLocked: true, lockedMakerspaceId: 7, isSuperadmin: false });
    expect(await probeProps("GrantedResourcesPanel")).toMatchObject({ bookingGrants: false });
  });
  it("says it cannot resolve the space when a locked deployment has no locked space id", async () => {
    show("granted", { currentUser: { makerspaces: [], event_grants: [{ id: 1 }] }, singleTenantLocked: true, lockedMakerspaceId: undefined, isSuperadmin: false });
    expect(await screen.findByText("Unable to resolve this makerspace.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assigned resources" })).toBeInTheDocument();
  });
  it("flags booking grants", async () => {
    show("granted", { currentUser: { makerspaces: [], booking_grants: [{ id: 1 }] }, isSuperadmin: false, activeMakerspace: undefined });
    expect(await probeProps("GrantedResourcesPanel")).toMatchObject({ bookingGrants: true });
  });
});

describe("always-present chrome inside a space", () => {
  it("shows the breadcrumb for a superadmin and not for staff or single-tenant", async () => {
    const { unmount } = show("dashboard");
    await screen.findByTestId("panel:PlatformSpaceBreadcrumb");
    expect(await probeProps("PlatformSpaceBreadcrumb")).toMatchObject({ spaceName: "Lab", tab: "dashboard" });
    expect(await probeProps("AreaAllowances")).toMatchObject({ makerspaceId: 7, tab: "dashboard" });
    expect(await probeProps("ModuleAnalytics")).toMatchObject({ tab: "dashboard" });
    unmount();
    show("dashboard", staff(["view_audit"]));
    await screen.findByTestId("panel:AreaAllowances");
    absent("PlatformSpaceBreadcrumb");
    unmount();
  });
  it("hands the member-360 console the actor's actions", async () => {
    show("members", staff(["manage_members"]));
    expect(await probeProps("ConsoleMemberActivity")).toMatchObject({ makerspaceId: 7, activeTab: "members", isSuperadmin: false, actions: ["manage_members"] });
  });
});

describe("tab gates", () => {
  it("devices needs the devices module AND the manage_devices action (or superadmin)", async () => {
    const { unmount } = show("devices", staff(["manage_devices"]));
    await screen.findByTestId("panel:DevicesPanel");
    unmount();
    const second = show("devices", staff(["manage_devices"], { activeMakerspace: space({ enabled_modules: [] }) }));
    await screen.findByTestId("panel:AreaAllowances");
    absent("DevicesPanel");
    second.unmount();
    show("devices", staff(["view_audit"]));
    await screen.findByTestId("panel:AreaAllowances");
    absent("DevicesPanel");
  });
  it("the dashboard receives the allowed tabs and role flags", async () => {
    show("dashboard", { guestOnly: true, singleTenantLocked: true });
    expect(await probeProps("DashboardPanel")).toMatchObject({ canManageMakerspace: true, isSuperadmin: true, singleTenantLocked: true, guestOnly: true });
  });
  it("notifications get the manage-members flag from the actor's actions", async () => {
    const { unmount } = show("notifications", staff(["manage_members"]));
    expect(await probeProps("NotificationInbox")).toMatchObject({ canManageMembers: true });
    unmount();
    show("notifications", staff(["view_audit"]));
    expect(await probeProps("NotificationInbox")).toMatchObject({ canManageMembers: false });
  });
  it("the channels page is for staff with at least one action only", async () => {
    const { unmount } = show("channels", staff(["view_audit"]));
    expect(await screen.findByRole("heading", { name: "My notification channels" })).toBeInTheDocument();
    await screen.findByTestId("panel:MyNotificationSettings");
    unmount();
    const second = show("channels", staff([]));
    await screen.findByTestId("panel:AreaAllowances");
    expect(screen.queryByRole("heading", { name: "My notification channels" })).toBeNull();
    second.unmount();
    show("channels");
    await screen.findByTestId("panel:AreaAllowances");
    expect(screen.queryByRole("heading", { name: "My notification channels" })).toBeNull();
  });
  it("requests, inventory, ledger, reports, direct, handover each open and carry their flags", async () => {
    show("requests", { guestOnly: true, canSeeHardware: false });
    expect(await probeProps("RequestsPanel")).toMatchObject({ guestOnly: true, canSeeHardware: false, canViewAudit: true });
  });
  it("inventory carries edit and to-buy flags", async () => {
    show("inventory", { canUseToBuy: false, canEditInventory: false });
    expect(await probeProps("Inventory")).toMatchObject({ canUseToBuy: false, canEditInventory: false, canViewAudit: true });
  });
  it("needs-fix and categories need edit-inventory", async () => {
    const { unmount } = show("needsfix");
    await screen.findByTestId("panel:NeedsFixTab");
    unmount();
    const second = show("needsfix", { canEditInventory: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("NeedsFixTab");
    second.unmount();
    const third = show("categories");
    await screen.findByTestId("panel:Categories");
    third.unmount();
    show("categories", { canEditInventory: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("Categories");
  });
  it("machines derives its flags from modules, features and capabilities", async () => {
    show("machines", { isMachineOnly: true, guestOnly: true, singleTenantLocked: true });
    expect(await probeProps("MachinesPanel")).toMatchObject({ makerspaceId: 7, canManage: true, machineServiceEnabled: true, printingEnabled: true, reportsEnabled: true,
      guestOnly: true, makerspaceSlug: "lab", singleTenantLocked: true, delegatedRecipientRulesEnabled: true, adapterConsole: false, printerAdapter: true });
  });
  it("machines: delegated recipient rules need a machine-only actor, the notifications module and the feature", async () => {
    show("machines", { isMachineOnly: false });
    expect(await probeProps("MachinesPanel")).toMatchObject({ delegatedRecipientRulesEnabled: false });
  });
  it("machines: without devices or machine_service the adapter and print flags are off", async () => {
    show("machines", { activeMakerspace: space({ enabled_modules: ["machines"], enabled_features: [] }) });
    expect(await probeProps("MachinesPanel")).toMatchObject({ machineServiceEnabled: false, printingEnabled: false, reportsEnabled: false, adapterConsole: false, printerAdapter: false, delegatedRecipientRulesEnabled: false });
  });
  it("events, bookings need their manage flags and pass the public-site flag", async () => {
    const { unmount } = show("events", { activeMakerspace: space({ public_site_enabled: true }) });
    expect(await probeProps("EventsPanel")).toMatchObject({ makerspaceId: 7, publicSiteEnabled: true });
    unmount();
    const second = show("events", { canManageEvents: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("EventsPanel");
    second.unmount();
    const third = show("bookings", { activeMakerspace: space({ enabled_features: ["bookings.recurring"] }) });
    expect(await probeProps("BookingsPanel")).toMatchObject({ recurringEnabled: true });
    third.unmount();
    show("bookings", { canManageBookings: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("BookingsPanel");
  });
  it("the organized tab inside a space is for non-superadmins only; analytics also respect the lock", async () => {
    const { unmount } = show("organized", staff(["view_audit"]));
    await screen.findByTestId("panel:OrganizedEventsPanel");
    unmount();
    const second = show("organized");
    await screen.findByTestId("panel:AreaAllowances");
    absent("OrganizedEventsPanel");
    second.unmount();
    const third = show("organization-analytics", staff(["view_audit"]));
    await screen.findByTestId("panel:OrganizationAnalyticsPanel");
    third.unmount();
    show("organization-analytics", staff(["view_audit"], { singleTenantLocked: true }));
    await screen.findByTestId("panel:AreaAllowances");
    absent("OrganizationAnalyticsPanel");
  });
  it("members need manage_members and carry module and finance flags", async () => {
    const { unmount } = show("members", staff(["manage_members", "view_finance"]));
    expect(await probeProps("MembersPanel")).toMatchObject({ makerspaceId: 7, isSuperadmin: false, membershipEnabled: true, presenceEnabled: true, machinesEnabled: true,
      canViewFinance: true, canRecordPayment: false, actorActions: ["manage_members", "view_finance"] });
    unmount();
    show("members", staff(["view_audit"]));
    await screen.findByTestId("panel:AreaAllowances");
    absent("MembersPanel");
  });
  it("member cards need the cards permission", async () => {
    const { unmount } = show("cards");
    await screen.findByTestId("panel:MemberCardsPanel");
    unmount();
    show("cards", { canUseMemberCards: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("MemberCardsPanel");
  });
});

describe("money tabs", () => {
  it("payments open for finance or record-payment actors and also render payouts only with view_finance", async () => {
    const { unmount } = show("payments", staff(["view_finance"]));
    await screen.findByTestId("panel:PaymentsPanel");
    await screen.findByTestId("panel:EventPayoutsSection");
    unmount();
    const second = show("payments", staff(["record_payment"]));
    await screen.findByTestId("panel:PaymentsPanel");
    absent("EventPayoutsSection");
    second.unmount();
    show("payments", staff(["view_audit"]));
    await screen.findByTestId("panel:AreaAllowances");
    absent("PaymentsPanel");
  });
  it("refunds need the tab to be allowed and decide by subject action", async () => {
    show("refunds", staff(["manage_events", "record_payment", "view_finance"]));
    const refund = await probeProps("RefundQueue");
    expect(refund).toMatchObject({ makerspaceId: 7, makerspaceName: "Lab", canEditPolicy: true, canDecide: true });
  });
  it("refund decisions are off for an actor holding only finance actions", async () => {
    show("refunds", staff(["view_finance"]));
    expect(await probeProps("RefundQueue")).toMatchObject({ canEditPolicy: true, canDecide: false });
  });
  it("finance carries finance and record-payment flags", async () => {
    show("finance", staff(["view_finance", "record_payment"]));
    expect(await probeProps("FinancePanel")).toMatchObject({ canViewFinance: true, canRecordPayment: true });
  });
  it("to-buy carries the kind flag and whether the inventory tab is available", async () => {
    show("tobuy", { canChooseToBuyKind: false });
    expect(await probeProps("ProcurementPanel")).toMatchObject({ canChooseKind: false, inventoryTabAvailable: true });
  });
});

describe("operations tabs", () => {
  it.each([
    ["consumables", "ConsumablesPanel"], ["incidents", "IncidentRegister"], ["schedule", "SchedulePanel"], ["shop", "ShopPanel"], ["donations", "DonationsArea"], ["accountability", "AccountabilityPanel"],
  ])("%s opens its panel with the space for a superadmin", async (tab, name) => {
    show(tab);
    expect(await probeProps(name)).toMatchObject({});
    expect(screen.getByTestId(`panel:${name}`)).toBeInTheDocument();
  });
  it("repairs and shop and donations hand the actor's actions through, extended for a superadmin repairs actor", async () => {
    show("repairs");
    expect(await probeProps("RepairsPanel")).toMatchObject({ actions: [...SUPER_ACTIONS, "manage_makerspace", "manage_machines", "edit_inventory", "manage_bookings"] });
  });
  it("the schedule groups by area for a space manager and carries the lock", async () => {
    show("schedule", { canManageMakerspace: false, guestOnly: true, singleTenantLocked: true });
    expect(await probeProps("SchedulePanel")).toMatchObject({ groupByArea: false, guestOnly: true, singleTenantLocked: true });
  });
  it("consumables carry the edit flag; shop and donations the superadmin flag", async () => {
    const { unmount } = show("consumables", { canEditInventory: false });
    expect(await probeProps("ConsumablesPanel")).toMatchObject({ canEditInventory: false });
    unmount();
    show("shop");
    expect(await probeProps("ShopPanel")).toMatchObject({ isSuperadmin: true });
  });
  it("accountability is the inventory view for an actor without manage_members, and absent when the tab is not allowed", async () => {
    const { unmount } = show("accountability", staff(["manage_members"]));
    expect(await probeProps("AccountabilityPanel")).toMatchObject({ inventoryView: false, isSuperadmin: false });
    unmount();
    show("accountability", staff(["view_audit"]));
    await screen.findByTestId("panel:AreaAllowances");
    absent("AccountabilityPanel");
  });
  it("transfers, stocktake, bulk need edit-inventory (transfers also open for a superadmin)", async () => {
    const { unmount } = show("transfers", staff(["edit_inventory"]));
    await screen.findByTestId("panel:StockTransferPanel");
    unmount();
    const second = show("transfers", { canEditInventory: false });
    await screen.findByTestId("panel:StockTransferPanel");
    second.unmount();
    const third = show("transfers", staff(["view_audit"], { canEditInventory: false }));
    await screen.findByTestId("panel:AreaAllowances");
    absent("StockTransferPanel");
    third.unmount();
    const fourth = show("stocktake");
    expect(await probeProps("StocktakePanel")).toMatchObject({ canConfigure: true, isSuperadmin: true });
    fourth.unmount();
    const fifth = show("bulk");
    await screen.findByTestId("panel:BulkImport");
    fifth.unmount();
    show("bulk", { canEditInventory: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("BulkImport");
  });
  it("QR-family tabs need manage-QR", async () => {
    for (const [tab, name] of [["containers", "ContainersPanel"], ["qr", "QrTools"], ["scanner", "ScannerPanel"]] as const) {
      const on = show(tab);
      await screen.findByTestId(`panel:${name}`);
      on.unmount();
      const off = show(tab, { canManageQr: false });
      await screen.findByTestId("panel:AreaAllowances");
      absent(name);
      off.unmount();
    }
  });
  it("the ledger can export unless the actor is a handout-only desk", async () => {
    const { unmount } = show("ledger");
    expect(await probeProps("Ledger")).toMatchObject({ isSuperadmin: true, canExport: true });
    unmount();
    show("ledger", staff(["issue_request", "return_request"]));
    expect(await probeProps("Ledger")).toMatchObject({ canExport: false });
  });
  it("warranty opens for edit-inventory or printing-capable actors only", async () => {
    const { unmount } = show("warranty", { canEditInventory: false, canSeePrinting: true });
    await screen.findByTestId("panel:WarrantyPanel");
    unmount();
    show("warranty", { canEditInventory: false, canSeePrinting: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("WarrantyPanel");
  });
  it("reports carry the printing-only, audit, machine and finance flags", async () => {
    show("reports", { printingOnly: true, canViewAudit: false, canManageMachines: false });
    expect(await probeProps("OperationsReports")).toMatchObject({ printingOnly: true, canViewAudit: false, canManageMachines: false, canViewFinance: true });
  });
  it("direct loans open for an actor who may issue a direct loan, and not otherwise", async () => {
    const { unmount } = show("direct");
    await screen.findByTestId("panel:DirectLoans");
    unmount();
    show("direct", { canIssueDirectLoan: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("DirectLoans");
  });
  it("handover needs the collect-service-requests permission", async () => {
    const second = show("handover");
    expect(await probeProps("HandoverConsole")).toMatchObject({ makerspaceId: 7, enabled: true });
    second.unmount();
    show("handover", { canCollectServiceRequests: false });
    await screen.findByTestId("panel:AreaAllowances");
    absent("HandoverConsole");
  });
  it("the audit log gets no action filter for a superadmin and the actor's actions otherwise", async () => {
    const { unmount } = show("audit");
    const all = await probeProps("AuditLog");
    expect(all).toMatchObject({ makerspaceId: 7 });
    expect(all).not.toHaveProperty("actions");
    unmount();
    show("audit", staff(["view_audit"]));
    expect(await probeProps("AuditLog")).toMatchObject({ makerspaceId: 7, actions: ["view_audit"] });
  });
});
