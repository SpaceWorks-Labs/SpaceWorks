import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { persistStaffTab, STAFF_ACTIVE_TAB_KEY } from "./staffTabs";
import { renderWorkspace, resetShellMocks, mocks, space, handout } from "../../../e2e/fixtures/staffShellHarness";

beforeEach(() => { setRouteSessionContext("person"); resetShellMocks(); });
const location = () => screen.getByTestId("location").textContent;
describe("StaffWorkspace route contracts", () => {
  it("W11 narrows content for handout actors while path building keeps raw guestOnly", () => {
    renderWorkspace("/m/lab/admin/requests", { actions: handout });
    expect(screen.getByTestId("tab")).toHaveTextContent("requests|true");
    expect(within(screen.getByRole("navigation", { name: "Staff sections" })).getByRole("link", { name: "Direct handout" })).toHaveAttribute("href", "/m/lab/admin/direct-handout");
  });
  it("W11 raw guest route also narrows content", () => {
    renderWorkspace("/guest-admin/requests", { guestOnly: true, singleTenantLocked: true });
    expect(screen.getByTestId("tab")).toHaveTextContent("requests|true");
  });
  it.each([
    ["known permission denial", { actions: ["manage_machines"] }],
    ["module denial", { activeMakerspace: space(1, "lab", { enabled_modules: ["machines"] }) }],
  ])("W12 preserves URL and renders denial without selected nav or content: %s", (_, props) => {
    renderWorkspace("/m/lab/admin/qr-tools", props);
    expect(location()).toBe("/m/lab/admin/qr-tools");
    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(screen.queryByTestId("tab")).toBeNull();
    expect(document.querySelector('[aria-current="page"]')).toBeNull();
    expect(screen.getByRole("link", { name: "Go to Dashboard" })).toHaveAttribute("href", "/m/lab/admin/dashboard");
  });
  it("W13 denied Requests redirects with the original search", () => {
    renderWorkspace("/m/lab/admin/requests?queue=pending", { actions: ["manage_machines"], isMachineOnly: true });
    expect(location()).toBe("/m/lab/admin/dashboard?queue=pending");
  });
  it.each([["inventory", "dashboard"], ["qr", "dashboard"]])("W14 baseline discrepancy: unknown route defaults even with stored %s", (stored, expected) => {
    persistStaffTab(stored);
    renderWorkspace("/m/lab/admin/nope?x=1", { actions: ["manage_makerspace", "view_inventory"] });
    expect(location()).toBe(`/m/lab/admin/${expected}?x=1`);
  });
  it("W15 canonicalisation preserves query and drops hash", () => {
    renderWorkspace("/admin/inventory?id=4&ordering=-name#row");
    expect(location()).toBe("/m/lab/admin/inventory?id=4&ordering=-name");
  });
  it.each([["/admin/printing", "/m/lab/admin/machines"], ["/m/lab/admin/printing/12-laser", "/m/lab/admin/machines/12-laser"]])("W16 canonicalises printing alias %s", (url, expected) => {
    renderWorkspace(url); expect(location()).toBe(expected);
  });
  it.each([["machines/12-laser", "machines/12-laser"], ["settings/lending", "settings/lending"], ["inventory/x", "inventory"]])("W17 preserves only machine and settings subpaths: %s", (url, expected) => {
    renderWorkspace(`/admin/${url}`); expect(location()).toBe(`/m/lab/admin/${expected}`);
  });
  it("W15b keeps a pre-split settings anchor for the Settings panel to resolve", () => {
    renderWorkspace("/admin/settings?x=1#integrations");
    expect(location()).toBe("/m/lab/admin/settings?x=1#integrations");
  });
  it("W18 never carries denied machine subpaths onto the fallback", () => {
    renderWorkspace("/admin/machines/12", { actions: ["manage_members"] });
    expect(location()).toBe("/admin/machines/12");
    expect(screen.getByRole("link", { name: "Go to Dashboard" })).toHaveAttribute("href", "/m/lab/admin/dashboard");
  });
  it("W19 platform console links retain platform context on unscoped routes", () => {
    renderWorkspace("/m/lab/admin/inventory", { isSuperadmin: true });
    expect(screen.getByRole("link", { name: "Organizations" })).toHaveAttribute("href", "/admin/organizations?context=platform");
    expect(screen.getByRole("link", { name: "Platform dashboard" })).toHaveAttribute("href", "/admin/platform-dashboard?context=platform");
    // #115: inside a chosen space the superadmin's tenant links keep the platform context too.
    expect(screen.getByRole("link", { name: "Items" })).toHaveAttribute("href", "/admin/inventory?context=platform");
    expect(screen.getByRole("link", { name: "Staff & roles" })).toHaveAttribute("href", "/admin/users?context=platform");
  });
  it("W25 unknown slug canonicalises to selected workspace", () => {
    renderWorkspace("/m/ghost/admin/inventory"); expect(location()).toBe("/m/lab/admin/inventory");
  });
  it.each([["tobuy", "to-buy"], ["printing", "machines"], ["nonsense", "dashboard"]])("W26 bare workspace restores stored %s", (stored, expected) => {
    localStorage.setItem(`${STAFF_ACTIVE_TAB_KEY}:person`, stored);
    renderWorkspace("/m/lab/admin"); expect(location()).toBe(`/m/lab/admin/${expected}`);
  });
  it("W37 denied routes retain only the unavailable heading and do not mount Home progress", () => {
    renderWorkspace("/m/lab/admin/qr-tools", { actions: ["manage_makerspace"] });
    expect(screen.queryByTestId("checklist")).not.toBeInTheDocument();
    expect(mocks.checklist).not.toHaveBeenCalled();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Page unavailable");
  });
  it("W38 all tab content receives the StaffListContext authority", () => {
    const { props } = renderWorkspace();
    expect(mocks.content).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ ownerName: "manager", canShare: true, actions: props.actions, isSuperadmin: false }));
  });
  it.each([[false, "/m/lab/admin/requests"], [true, "/guest-admin/requests"]])("W45 pins guest-admin canonicalisation singleTenantLocked=%s", (singleTenantLocked, expected) => {
    renderWorkspace("/guest-admin/requests", { guestOnly: true, singleTenantLocked }); expect(location()).toBe(expected);
  });
});
