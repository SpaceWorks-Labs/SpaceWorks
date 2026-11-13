import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { inboxUnreadKey } from "../notifications/PersonalInbox";
import { TAB_LABELS, STAFF_TAB_KEYS } from "./staffAccess";
import { sidebarSections, SIDEBAR_SECTIONS } from "./sidebarSections";
import { renderWorkspace, resetShellMocks, mocks, space, handout, queryClient, user } from "../../../e2e/fixtures/staffShellHarness";

beforeEach(() => { setRouteSessionContext("person"); resetShellMocks(); });
const nav = () => within(screen.getByRole("navigation", { name: "Staff sections" }));
const unreadCalls = () => mocks.request.mock.calls.filter(([path]) => String(path).endsWith("/unread-count"));
describe("StaffWorkspace shell contracts", () => {
  it("W1 Home is shell copy while the palette retains Dashboard", () => {
    renderWorkspace("/m/lab/admin/dashboard");
    expect(nav().getByRole("link", { name: "Home" })).toHaveAttribute("href", "/m/lab/admin/dashboard");
    expect(TAB_LABELS.dashboard).toBe("Dashboard");
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(screen.getByRole("option", { name: "Go to Dashboard" })).toBeInTheDocument();
  });
  it("W2 handout-only navigation is flat and limited to its operational destinations", () => {
    renderWorkspace("/m/lab/admin/requests", { actions: handout });
    expect(nav().getAllByRole("link").filter(link => !link.textContent?.includes("View public")).map(link => link.textContent)).toEqual(["Home", "Requests", "Direct handout", "Pickups (Handover)", "Payments", "Inbox"]);
    expect(nav().queryByRole("heading")).toBeNull();
    expect(screen.getByRole("navigation", { name: "Staff quick navigation" })).toBeInTheDocument();
  });
  it("W3 collect-only lands on Home with job pickups and personal notifications", () => {
    renderWorkspace("/admin", { actions: ["collect_service_request"], activeMakerspace: space(1, "lab", { enabled_modules: ["machine_service", "notifications"] }) });
    expect(screen.getByTestId("location")).toHaveTextContent("/m/lab/admin/dashboard");
    expect(nav().getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    expect(nav().getAllByRole("link").filter(link => !link.textContent?.includes("View public")).map(link => link.textContent)).toEqual(["Home", "Pickups (Handover)", "Inbox"]);
    expect(nav().queryByRole("link", { name: "Requests" })).toBeNull();
  });
  it("W4 governance-only is global and has no palette or job tray", () => {
    renderWorkspace("/admin", { actions: [], activeMakerspace: undefined, selected: null });
    expect(screen.getByTestId("location")).toHaveTextContent("/admin/organizations");
    expect(nav().getAllByRole("link").map(link => link.textContent)).toEqual(["Organizations", "Organized events", "Org analytics"]);
    expect(screen.queryByTestId("jobs")).toBeNull();
    expect(screen.queryByRole("button", { name: "Search and commands" })).toBeNull();
  });
  it("W5 single-tenant hides switching and cross-venue/platform tabs and uses public root", () => {
    renderWorkspace("/admin/inventory", { singleTenantLocked: true, isSuperadmin: true });
    expect(screen.queryByRole("button", { name: "Switch makerspace" })).toBeNull();
    for (const name of ["Organizations", "Platform dashboard", "Platform settings", "Organized events", "Org analytics"]) expect(nav().queryByRole("link", { name })).toBeNull();
    expect(nav().getByRole("link", { name: /View public page/ })).toHaveAttribute("href", "/");
  });
  it("W6 W9 central switcher lists every makerspace, calls selection and excludes superadmin reset", () => {
    const { props } = renderWorkspace();
    fireEvent.click(screen.getAllByRole("button", { name: /Community Lab.*Space Manager/ })[0]);
    fireEvent.click(screen.getByRole("button", { name: "B" }));
    expect(props.setSelected).toHaveBeenCalledWith(2);
    expect(screen.queryByRole("button", { name: "Switch makerspace" })).toBeNull();
  });
  it("W7 one makerspace is a static workspace card", () => {
    renderWorkspace(undefined, { makerspaces: [space()] });
    expect(screen.queryByRole("button", { name: /Community Lab.*Space Manager/ })).toBeNull();
  });
  it("W10 superadmin role wins over a local membership role", () => {
    renderWorkspace(undefined, { isSuperadmin: true, user: user() });
    expect(screen.getAllByRole("button", { name: /Community Lab.*Super Admin/ })).toHaveLength(1);
  });
  it("W20 no-workspace global routes have only global links and no unread/search/jobs", () => {
    renderWorkspace("/admin/platform-dashboard", { isSuperadmin: true, activeMakerspace: undefined, selected: null });
    expect(screen.getAllByText("Choose a space").length).toBeGreaterThan(0);
    expect(nav().getAllByRole("link").every(link => link.getAttribute("href")?.startsWith("/admin/"))).toBe(true);
    expect(nav().queryByRole("link", { name: "Items" })).toBeNull();
    expect(screen.queryByTestId("jobs")).toBeNull();
    expect(screen.queryByRole("button", { name: "Search and commands" })).toBeNull();
    expect(unreadCalls()).toHaveLength(0);
  });
  it("W27 clicking navigation persists the tab through setTab", () => {
    const { props } = renderWorkspace(); fireEvent.click(nav().getByRole("link", { name: "Requests" }));
    expect(props.setTab).toHaveBeenCalledWith("requests");
  });
  it("W28 W30 W31 one shared unread query feeds Inbox and the closed-drawer trigger", async () => {
    renderWorkspace();
    const inbox = await nav().findByRole("link", { name: "Inbox 3 unread" });
    expect(within(inbox).getByText("3", { exact: true })).toBeVisible();
    expect(screen.getByRole("button", { name: "Open navigation, 3 need attention" })).toBeInTheDocument();
    expect(unreadCalls()).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation, 3 need attention" }));
    expect(unreadCalls()).toHaveLength(1);
  });
  it.each([undefined, []])("W29 does not fetch unread when space or module is absent (%s)", modules => {
    renderWorkspace(modules ? "/m/lab/admin/inventory" : "/admin/organizations", modules ? { activeMakerspace: space(1, "lab", { enabled_modules: [] }) } : { activeMakerspace: undefined, actions: [] });
    expect(unreadCalls()).toHaveLength(0);
  });
  it("W32 skip link is first and nav is outside the focusable main region", () => {
    renderWorkspace();
    expect(document.querySelector('a,button,input')).toHaveTextContent("Skip to main content");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("main").querySelector("nav")).toBeNull();
  });
  it("W33 Ctrl/Cmd K opens with the mobile drawer closed", () => {
    renderWorkspace();
    fireEvent.keyDown(document, { key: "k", ctrlKey: true }); expect(screen.getByRole("combobox")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.keyDown(document, { key: "k", metaKey: true }); expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
  it("W33 Ctrl K closes the navigation drawer before opening the palette", async () => {
    renderWorkspace(); fireEvent.click(screen.getByRole("button", { name: /Open navigation/ }));
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    await waitFor(() => expect(screen.getByRole("combobox")).toBeInTheDocument());
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
  });
  it("W34 palette does not open above another dialog", () => {
    renderWorkspace(); const dialog = document.createElement("div"); dialog.setAttribute("role", "dialog"); document.body.append(dialog);
    fireEvent.keyDown(document, { key: "k", ctrlKey: true }); expect(screen.queryByRole("combobox")).toBeNull(); dialog.remove();
  });
  it("W35 palette omits forbidden hits and filters quick create", async () => {
    mocks.request.mockResolvedValue({ results: [{ entity: "users", id: 9, label: "Forbidden", tab: "users", query: {} }] });
    renderWorkspace("/m/lab/admin/requests", { actions: handout });
    fireEvent.keyDown(document, { key: "k", ctrlKey: true }); const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "Forbidden" } });
    await waitFor(() => expect(mocks.request.mock.calls.some(([path]) => String(path).includes("/admin/search"))).toBe(true));
    expect(screen.queryByRole("option", { name: /Forbidden/ })).toBeNull();
    fireEvent.change(input, { target: { value: "New" } }); expect(screen.queryByRole("option", { name: "New item" })).toBeNull();
  });
  it("W36 job tray is in the sidebar bottom block (wave 2b overrides former first-in-main position)", () => {
    renderWorkspace(); expect(screen.getAllByTestId("jobs").some(node => node.closest("aside"))).toBe(true);
    // Below lg the sidebar lives in the drawer, so a compact-only copy surfaces in main.
    const inMain = screen.getByRole("main").querySelector('[data-testid="jobs"]');
    expect(inMain?.closest(".lg\\:hidden")).toBeTruthy();
  });
  it("W40 public-page link exists only with an active space", () => {
    renderWorkspace(); expect(nav().getByRole("link", { name: /View public page/ })).toHaveAttribute("href", "/m/lab");
  });
  it("W41 Sign out stays a button in the user disclosure and calls signOut", () => {
    const { props } = renderWorkspace(); fireEvent.click(screen.getAllByRole("button", { name: /manager Space Manager/ })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" })); expect(props.signOut).toHaveBeenCalledOnce();
  });
  it("W42 panel supplies exactly one h1 without a duplicate host heading", () => {
    renderWorkspace(); expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Inventory");
  });
  it("W43 route navigation closes drawer and focuses main", async () => {
    renderWorkspace(); fireEvent.click(screen.getByRole("button", { name: /Open navigation/ }));
    const drawer = screen.getByRole("dialog", { name: "Navigation" });
    fireEvent.click(within(drawer).getByRole("link", { name: "Requests" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
  });
  it("W44 renders when matchMedia is absent", () => { expect(window.matchMedia).toBeUndefined(); renderWorkspace(); expect(nav().getByRole("link", { name: "Items" })).toBeInTheDocument(); });
  it("maps all 42 keys exactly once with the Settings family and Across venues caption", () => {
    // "channels" (My channels) lives in the account menu, not the sidebar (0.12.0 row 10).
    expect(SIDEBAR_SECTIONS.flatMap(section => [...section.tabs, ...section.more ?? []]).sort()).toEqual(STAFF_TAB_KEYS.filter(key => key !== "channels").sort());
    expect(sidebarSections(["settings", "emailtemplates"], "emailtemplates")[0].items[0]).toMatchObject({ label: "Settings", href: "/admin/settings", children: [{ key: "settings" }, { key: "emailtemplates" }] });
    // Without Settings or Security there is no family: an area manager's pages sit flat under Tools.
    expect(sidebarSections(["emailtemplates"], "emailtemplates")[0]).toMatchObject({ label: "Tools", items: [{ key: "emailtemplates" }] });
    // The Across venues caption belongs to the generic menu; the Space Manager menu files Organizations under People.
    renderWorkspace(undefined, { actions: ["view_inventory", "edit_inventory"] }); expect(nav().getByText("Across venues")).toBeInTheDocument();
  });
  it("Requests needs-action badge uses only cached permitted dashboard counts", () => {
    const client = queryClient(); client.setQueryData(["dashboard", 1], { pending_requests: 2, awaiting_issue: 4 });
    renderWorkspace(undefined, {}, client); expect(nav().getByRole("link", { name: "Requests 6 needs action" })).toBeInTheDocument();
    expect(mocks.request.mock.calls.some(([path]) => String(path).endsWith("/dashboard"))).toBe(false);
  });
  it("machine types reuse cached id-based subpaths, cap at eight and include All types", () => {
    const client = queryClient(); client.setQueryData(["machine-types", 1], Array.from({ length: 9 }, (_, i) => ({ id: i + 1, slug: "laser", name: `Type ${i + 1}` })));
    renderWorkspace("/m/lab/admin/machines/2-laser", { actions: ["manage_machines"], isMachineOnly: true }, client);
    expect(nav().getByRole("link", { name: "Type 2" })).toHaveAttribute("aria-current", "page");
    expect(nav().queryByRole("link", { name: "Type 9" })).toBeNull(); expect(nav().getByRole("link", { name: "All types →" })).toBeInTheDocument();
    expect(mocks.request.mock.calls.some(([path]) => String(path).includes("machine-types"))).toBe(false);
  });
});

it("W28 unread key and polling options are shared with PersonalInbox; cache updates refresh the badge", async () => {
  const { client } = renderWorkspace(); await nav().findByRole("link", { name: "Inbox 3 unread" });
  const query = client.getQueryCache().find({ queryKey: inboxUnreadKey(1), exact: true });
  expect(query?.options.retry).toBe(false);
  expect(query?.getObserversCount()).toBe(1);
  act(() => client.setQueryData(inboxUnreadKey(1), { count: 9 }));
  expect(await nav().findByRole("link", { name: "Inbox 9 unread" })).toBeInTheDocument();
});
it("W28 unread failures show zero and are not retried", async () => {
  mocks.request.mockRejectedValue(new Error("Offline")); renderWorkspace();
  await waitFor(() => expect(unreadCalls()).toHaveLength(1));
  expect(nav().getByRole("link", { name: "Inbox" })).toBeInTheDocument();
});
it("W30 large unread counts display 99+ while the accessible name retains the real count", async () => {
  mocks.request.mockResolvedValue({ count: 123 }); renderWorkspace();
  const inbox = await nav().findByRole("link", { name: "Inbox 99+ (123 unread)" });
  expect(within(inbox).getByText("99+", { exact: true })).toBeVisible();
});
it("Requests never uses stale dashboard data for an actor who cannot read dashboard", () => {
  const client = queryClient(); client.setQueryData(["dashboard", 1], { pending_requests: 9, awaiting_issue: 5 });
  renderWorkspace("/m/lab/admin/requests", { actions: ["issue_request", "manage_qr"] }, client);
  expect(nav().queryByRole("link", { name: "Home" })).toBeNull();
  expect(nav().getByRole("link", { name: "Requests" })).toBeInTheDocument();
});
