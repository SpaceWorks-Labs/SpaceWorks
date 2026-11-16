import type { ComponentProps, ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { StaffTabContent } from "./StaffTabContent";
import { StaffPlatformTabContent } from "./StaffPlatformTabContent";
import { PlatformConsoleContent } from "./platformConsole/PlatformConsoleContent";

const mocks = vi.hoisted(() => ({ dashboard: vi.fn(), payments: vi.fn(), procurement: vi.fn(), platform: vi.fn() }));
vi.mock("./panels/ModuleAnalytics", () => ({ ModuleAnalytics: () => null }));
// The per-area allowances strip (decision 242) is covered by AreaAllowances.test.tsx; it needs a QueryClient this wiring test does not provide.
vi.mock("./allowances/AreaAllowances", () => ({ AreaAllowances: () => null }));
vi.mock("./StaffTabLoaders", async original => ({ ...await original<typeof import("./StaffTabLoaders")>(),
  DashboardPanel: (props: { progress?: ReactNode }) => { mocks.dashboard(props); return <>{props.progress}</>; },
  PaymentsPanel: (props: unknown) => { mocks.payments(props); return null; },
  ProcurementPanel: (props: unknown) => { mocks.procurement(props); return null; },
  PlatformSettingsPanel: (props: unknown) => { mocks.platform(props); return null; },
}));

function props(actions: string[], tab = "dashboard", overrides: Partial<ComponentProps<typeof StaffTabContent>> = {}) {
  return {
    activeTab: tab, activeMakerspace: { id: 7, name: "Forge", slug: "forge" },
    currentUser: { username: "manager", makerspaces: [{ id: 8, actions: ["manage_makerspace"] }, { id: 7, actions }] },
    makerspaces: [], isSuperadmin: false, isMachineOnly: false, singleTenantLocked: false,
    ...overrides,
  } as ComponentProps<typeof StaffTabContent>;
}
beforeEach(() => vi.clearAllMocks());
it("passes the active membership authority and Home progress into Dashboard", () => {
  const actions = ["issue_request", "view_audit"];
  render(<MemoryRouter><StaffTabContent {...props(actions, "dashboard", { progress: <p>Setup progress</p> })} /></MemoryRouter>);
  expect(mocks.dashboard).toHaveBeenCalledWith(expect.objectContaining({ actions, isSuperadmin: false }));
  expect(screen.getByText("Setup progress")).toBeVisible();
});
it("passes the superadmin's per-space actions into Dashboard (#115)", () => {
  const superadminActions = ["manage_makerspace", "view_audit", "view_finance"];
  const base = props([], "dashboard");
  render(<MemoryRouter><StaffTabContent {...base} isSuperadmin
    currentUser={{ ...base.currentUser, makerspaces: [], superadmin_actions: superadminActions }} /></MemoryRouter>);
  expect(mocks.dashboard).toHaveBeenCalledWith(expect.objectContaining({ actions: superadminActions, isSuperadmin: true }));
});
it("passes the selected makerspace name to Payments", () => {
  render(<MemoryRouter><StaffTabContent {...props(["view_finance"], "payments")} /></MemoryRouter>);
  expect(mocks.payments).toHaveBeenCalledWith(expect.objectContaining({ makerspaceId: 7, makerspaceName: "Forge" }));
});
it.each([
  [[], undefined, false],
  [["view_inventory"], undefined, true],
  [["view_inventory"], [], true],
  [["view_inventory"], ["public_inventory"], true],
])("passes existing Inventory tab availability for actions=%s modules=%s", (actions, modules, available) => {
  const input = props(actions as string[], "tobuy");
  input.activeMakerspace = { ...input.activeMakerspace!, enabled_modules: modules as string[] | undefined };
  render(<MemoryRouter><StaffTabContent {...input} /></MemoryRouter>);
  expect(mocks.procurement).toHaveBeenCalledWith(expect.objectContaining({ inventoryTabAvailable: available }));
});
it.each([true, false])("renders one platform settings screen with platform hosting=%s", platformHosting => {
  const input = props([], "platform", { isSuperadmin: true });
  // 0.12.0: platform settings open without a chosen space, through the platform console content.
  render(<MemoryRouter><PlatformConsoleContent activeTab="platform" makerspaces={[{ ...input.activeMakerspace!, platform_hosting: platformHosting }]}
    currentUser={input.currentUser} onAuthRefresh={() => {}} /></MemoryRouter>);
  // #190 (48a7e674): the screen also learns which tombstoned apps hide their sections.
  expect(mocks.platform).toHaveBeenCalledWith({ platformHosting, unavailableApps: [] });
});
it("no longer renders platform settings from a space's platform tab content", () => {
  const input = props([], "platform", { isSuperadmin: true });
  render(<MemoryRouter><StaffPlatformTabContent activeTab="platform" activeMakerspace={input.activeMakerspace!} makerspaces={[]} isSuperadmin canManageMakerspace currentUser={input.currentUser} onAuthRefresh={() => {}} /></MemoryRouter>);
  expect(mocks.platform).not.toHaveBeenCalled();
});
