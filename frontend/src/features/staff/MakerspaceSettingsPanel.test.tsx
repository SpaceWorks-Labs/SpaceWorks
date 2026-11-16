import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { MakerspaceSettingsPanel } from "./MakerspaceSettingsPanel";
import type { Makerspace } from "./StaffPanels";
const { query, retry } = vi.hoisted(() => ({ query: vi.fn(), retry: vi.fn() }));
vi.mock("./StaffPanels", () => ({ useStaffGet: query }));
vi.mock("./ApiClientsTelegramSettings", () => ({ ApiClientsTelegramSettings: () => null }));
vi.mock("./MakerspaceBrandingSettings", () => ({ MakerspaceBrandingSettings: () => null }));
vi.mock("./MakerspaceBookingRulesSettings", () => ({ MakerspaceBookingRulesSettings: () => null }));
vi.mock("./MakerspaceBookingSettings", () => ({ MakerspaceBookingSettings: () => null }));
vi.mock("./MakerspaceReminderSettings", () => ({ MakerspaceReminderSettings: () => null }));
vi.mock("./MakerspaceCustomDomainSettings", () => ({ MakerspaceCustomDomainSettings: () => null }));
vi.mock("./MakerspaceEmailSettings", () => ({ MakerspaceEmailSettings: () => null }));
vi.mock("./MakerspaceFilamentSettings", () => ({ MakerspaceFilamentSettings: () => null }));
vi.mock("./MakerspaceFeatureSettings", () => ({ MakerspaceFeatureSettings: () => null }));
vi.mock("./MakerspaceGeofenceSettings", () => ({ MakerspaceGeofenceSettings: () => <p>Geofence editor</p> }));
vi.mock("../presence/PresencePrivacySettings", () => ({ PresencePrivacySettings: ({ makerspaceId, slug }: { makerspaceId: number; slug?: string }) => <p>Presence privacy editor {makerspaceId} {slug}</p> }));
// A draft the editor has not saved yet renders the shared SettingsActions bar.
vi.mock("./MakerspaceGeneralSettings", async () => {
  const { SettingsActions } = await import("../../components/ui");
  return { MakerspaceGeneralSettings: () => <SettingsActions onDiscard={() => undefined} /> };
});
vi.mock("./IntegrationHealthPanel", () => ({ IntegrationHealthPanel: () => <p>Health checks</p> }));
vi.mock("./KioskStationSettings", () => ({ KioskStationSettings: () => null }));
vi.mock("./MakerspaceLocationSettings", () => ({ MakerspaceLocationSettings: () => null }));
vi.mock("./MakerspaceProfileSettings", () => ({ MakerspaceProfileSettings: () => null }));
vi.mock("./BillingDocumentsSettings", () => ({ BillingDocumentsSettings: () => null }));
vi.mock("./SpacePacksPanel", () => ({ SpacePacksPanel: () => null }));
vi.mock("./MakerspaceMembershipSettings", () => ({ MakerspaceMembershipSettings: () => null }));
vi.mock("./MakerspacePaymentSettings", () => ({ MakerspacePaymentSettings: () => <p>Payment settings</p> }));
vi.mock("./MakerspacePublicStatsSettings", () => ({ MakerspacePublicStatsSettings: () => null }));
vi.mock("../stats/settings/PublicStatsSettingsPanel", () => ({ PublicStatsSettingsPanel: () => null }));
vi.mock("./MakerspaceSubdomainSettings", () => ({ MakerspaceSubdomainSettings: () => null }));
vi.mock("./MakerspaceWebhookSettings", () => ({ MakerspaceWebhookSettings: () => <p>Webhook editor</p> }));
vi.mock("./MakerspaceArchiveRequestPanel", () => ({ MakerspaceArchiveRequestPanel: () => <p>Archive workflow</p> }));
vi.mock("./NotificationTimingSettings", () => ({ NotificationTimingSettings: () => null }));
vi.mock("./NotificationDestinations", () => ({ NotificationDestinations: () => null }));
vi.mock("./EvidenceRetentionPanel", () => ({ EvidenceRetentionPanel: () => null }));
vi.mock("./NotificationMuteMatrix", () => ({ NotificationMuteMatrix: () => null }));
vi.mock("./NotificationRecipientPicker", () => ({ NotificationRecipientPicker: () => null }));
vi.mock("./pricing/PricingSettings", () => ({ PricingSettings: () => <p>Pricing editor</p> }));
vi.mock("./SettingsAuthorityCard", () => ({ SettingsAuthorityCard: () => null }));
vi.mock("../notifications/channelsApi", () => ({ useChannels: () => ({ data: undefined }) }));
const hosting = vi.hoisted(() => ({ available: false, calls: [] as boolean[] }));
vi.mock("../hosting/hostingApi", () => ({ useHostingAvailability: (enabled = true) => { hosting.calls.push(enabled); return enabled && hosting.available; } }));
vi.mock("./HostingInvitations", () => ({ HostingInvitations: ({ scope }: { scope: { makerspaceId: number } }) => <p>Hosting invitations for {scope.makerspaceId}</p> }));
vi.mock("./MakerspaceLoanPolicySettings", () => ({ MakerspaceLoanPolicySettings: () => <p>Loan policy editor</p> }));
vi.mock("../notifications/ChannelSetupPanel", () => ({ ChannelSetupPanel: () => <p>Channel setup</p> }));
vi.mock("../notifications/ChannelDeliveryLog", () => ({ ChannelDeliveryLog: () => <p>Channel deliveries</p> }));
// The modules whose settings sections are shown only while they are on (#183B).
const makerspace = { id: 7, name: "Community lab", slug: "lab", enabled_modules: ["staff_admin", "membership", "bookings", "machines"], enabled_features: ["loans.enabled"] } as unknown as Makerspace;
beforeEach(() => { hosting.available = false; hosting.calls = []; query.mockReturnValue({ data: makerspace, isLoading: false, error: null, refetch: retry }); retry.mockClear(); });
const BASE = "/m/lab/admin/settings";
function Where() { const location = useLocation(); return <output data-testid="where">{location.pathname}</output>; }
function mount({ path = `${BASE}/overview`, canManageMakerspace = true, space = makerspace, allowedTabs = [] as string[], isSuperadmin = false } = {}) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[path]}>
    <MakerspaceSettingsPanel makerspace={space} isSuperadmin={isSuperadmin} canManageMakerspace={canManageMakerspace} allowedTabs={allowedTabs} />
    <Where />
  </MemoryRouter></QueryClientProvider>);
}
const where = () => screen.getByTestId("where").textContent;
const nav = () => within(screen.getByRole("navigation", { name: "Settings pages" }));
const navIds = () => nav().getAllByRole("link").map(link => link.getAttribute("href")!.replace(`${BASE}/`, ""));

it("keeps one page heading and links every settings page as its own route", () => {
  mount();
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(screen.getByRole("heading", { level: 1, name: "Makerspace settings" })).toBeVisible();
  // Decision 255: grouped by the owner's mental model, Space → People → Areas → Money → Communication → Integrations → Administration.
  // Parity O-F1: "units" (Settings › People › Member units) sits beside Membership while that module is installed.
  expect(navIds()).toEqual(["overview", "general", "branding", "public-page", "public-stats", "membership", "units", "features", "lending",
    "materials", "bookings", "money", "notifications", "channels", "integrations", "health", "privacy"]);
  expect(nav().getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  for (const group of ["Space", "People", "Areas", "Money", "Communication", "Integrations", "Administration"]) expect(nav().getByRole("list", { name: group })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View public site" })).toHaveAttribute("href", "/m/lab");
});
it("renders only the open page's section and moves between pages through the router", () => {
  mount({ path: `${BASE}/integrations` });
  expect(screen.getByText("Webhook editor")).toBeInTheDocument();
  expect(screen.queryByText("Health checks")).toBeNull();
  expect(screen.queryByText("Payment settings")).toBeNull();
  fireEvent.click(nav().getByRole("link", { name: "Integration health" }));
  expect(where()).toBe(`${BASE}/health`);
  expect(screen.getByText("Health checks")).toBeInTheDocument();
  expect(screen.queryByText("Webhook editor")).toBeNull();
});
it.each([[BASE, "overview"], [`${BASE}#integrations`, "integrations"], [`${BASE}#start`, "overview"], [`${BASE}#bookings`, "bookings"], [`${BASE}#nope`, "overview"]])(
  "redirects %s to the %s page", (path, section) => {
    mount({ path });
    expect(where()).toBe(`${BASE}/${section}`);
  });
it("lands a superadmin on unscoped settings paths", () => {
  mount({ path: "/admin/settings", isSuperadmin: true });
  expect(where()).toBe("/admin/settings/overview");
});
it("explains a page that is hidden for this space or role instead of rendering it", () => {
  mount({ path: `${BASE}/channels`, canManageMakerspace: false });
  expect(screen.queryByText("Channel setup")).toBeNull();
  expect(screen.getByText("This settings page isn't available")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to settings overview" })).toHaveAttribute("href", `${BASE}/overview`);
  expect(navIds()).not.toContain("channels");
});
it("opens the existing archive workflow from the danger zone on the profile page only", () => {
  mount({ path: `${BASE}/general` });
  expect(screen.queryByText("Archive workflow")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Request archival/ }));
  expect(screen.getByRole("dialog", { name: "Archive this makerspace" })).toBeVisible();
  expect(screen.getByText("Archive workflow")).toBeVisible();
});
it("keeps archival off other pages and away from staff without the original permission", () => {
  const { unmount } = mount({ path: `${BASE}/money` });
  expect(screen.queryByRole("button", { name: /Request archival/ })).toBeNull();
  unmount();
  mount({ path: `${BASE}/general`, canManageMakerspace: false });
  expect(screen.queryByRole("button", { name: /Request archival/ })).toBeNull();
});
it("offers a retry when makerspace settings cannot load", () => {
  query.mockReturnValue({ data: undefined, isLoading: false, error: new Error("Offline"), refetch: retry });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalledOnce();
});
it("asks before leaving a page whose editor holds unsaved changes", () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  try {
    mount({ path: `${BASE}/general` });
    fireEvent.click(nav().getByRole("link", { name: "Payments & billing" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(where()).toBe(`${BASE}/general`);
    confirm.mockReturnValue(true);
    fireEvent.click(nav().getByRole("link", { name: "Payments & billing" }));
    expect(where()).toBe(`${BASE}/money`);
    confirm.mockClear();
    fireEvent.click(nav().getByRole("link", { name: "Notifications" }));
    expect(confirm).not.toHaveBeenCalled();
  } finally { confirm.mockRestore(); }
});
it("offers a grouped phone select that navigates to each settings page", () => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: /max-width: 767px/.test(query), addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  try {
    mount();
    const select = screen.getByRole("combobox", { name: "Settings page" });
    expect(Array.from(select.querySelectorAll("optgroup")).map(group => group.label)).toEqual(["Space", "People", "Areas", "Money", "Communication", "Integrations", "Administration"]);
    fireEvent.change(select, { target: { value: "money" } });
    expect(where()).toBe(`${BASE}/money`);
  } finally { vi.unstubAllGlobals(); }
});

it("puts the hub on the overview, channel setup and the loan policy on their own pages", () => {
  const full = { ...makerspace, enabled_modules: ["staff_admin", "notifications", "request_workflow"] } as unknown as Makerspace;
  query.mockReturnValue({ data: full, isLoading: false, error: null, refetch: retry });
  const { unmount } = mount({ space: full, allowedTabs: ["users"] });
  expect(screen.getByRole("searchbox", { name: "Search settings" })).toBeInTheDocument();
  expect(screen.queryByText("Channel setup")).toBeNull();
  unmount();
  const lending = mount({ space: full, path: `${BASE}/lending` });
  expect(lending.container.querySelector("#lending")).toHaveTextContent("Loan policy editor");
  lending.unmount();
  mount({ space: full, path: `${BASE}/channels` });
  expect(screen.getByText("Channel setup")).toBeInTheDocument();
});
// Decision 255: the retired Admin tools page folded into the menu; its old URL lands on the overview.
it("redirects the retired Admin tools page to the overview", () => {
  mount({ path: `${BASE}/tools`, allowedTabs: ["modules"] });
  expect(where()).toBe(`${BASE}/overview`);
});
it("lists the pages that live on their own console tab in their group, marked as leaving settings", () => {
  mount({ allowedTabs: ["modules", "security", "exports", "users", "shop", "inventory"] });
  const areas = within(nav().getByRole("list", { name: "Areas" }));
  expect(areas.getByRole("link", { name: /Areas & add-ons.*opens its own page/ })).toHaveAttribute("href", "/m/lab/admin/modules");
  expect(areas.getByRole("link", { name: /^Shop/ })).toHaveAttribute("href", "/m/lab/admin/shop/settings");
  expect(within(nav().getByRole("list", { name: "People" })).getByRole("link", { name: /Staff & roles/ })).toHaveAttribute("href", "/m/lab/admin/users");
  const admin = within(nav().getByRole("list", { name: "Administration" }));
  expect(admin.getByRole("link", { name: /Security/ })).toHaveAttribute("href", "/m/lab/admin/security");
  expect(admin.getByRole("link", { name: /Data export/ })).toHaveAttribute("href", "/m/lab/admin/data-export");
  // Only tabs the actor may open: no API access, audit log or backups here.
  expect(nav().queryByRole("link", { name: /API access|Audit log|Backup/ })).toBeNull();
});
it("shows each page's one-line help and links an area's own settings dialog", () => {
  mount({ path: `${BASE}/lending`, allowedTabs: ["inventory"] });
  expect(screen.getByText("Loan period, renewals, borrow limits, who can request, reminders and kiosks.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open Inventory settings" })).toHaveAttribute("href", "/m/lab/admin/inventory?settings=open");
});
it("keeps email sending under Communication and webhooks under Integrations", () => {
  const withEmail = { ...makerspace, enabled_modules: [...(makerspace.enabled_modules ?? []), "email"] } as unknown as Makerspace;
  query.mockReturnValue({ data: withEmail, isLoading: false, error: null, refetch: retry });
  mount({ space: withEmail });
  expect(within(nav().getByRole("list", { name: "Communication" })).getByRole("link", { name: "Email sending" })).toHaveAttribute("href", `${BASE}/email`);
  expect(within(nav().getByRole("list", { name: "Integrations" })).getByRole("link", { name: "Webhooks" })).toHaveAttribute("href", `${BASE}/integrations`);
});

it.each([[true, true], [true, false], [false, true], [false, false]])(
  "gates presence privacy and its search result (module=%s, manager=%s)", (presence, manager) => {
    const space = { ...makerspace, enabled_modules: presence ? ["presence"] : [] } as unknown as Makerspace;
    query.mockReturnValue({ data: space, isLoading: false, error: null });
    const { unmount } = mount({ canManageMakerspace: manager, space });
    fireEvent.change(screen.getByRole("searchbox", { name: "Search settings" }), { target: { value: "display names" } });
    const link = screen.queryByRole("link", { name: /Presence privacy.*Show names/ });
    if (presence && manager) expect(link).toHaveAttribute("href", `${BASE}/presence`);
    else expect(link).toBeNull();
    unmount();
    mount({ canManageMakerspace: manager, space, path: `${BASE}/presence` });
    expect(Boolean(screen.queryByText("Presence privacy editor 7 lab"))).toBe(presence && manager);
  },
);

it("adds the hosting invitation page only for managers while hosting requests are open", () => {
  hosting.available = true;
  const { unmount } = mount({ path: `${BASE}/hosting` });
  expect(navIds()).toContain("hosting");
  expect(screen.getByText("Hosting invitations for 7")).toBeInTheDocument();
  unmount();
  hosting.calls = [];
  mount({ path: `${BASE}/hosting`, canManageMakerspace: false });
  expect(navIds()).not.toContain("hosting");
  expect(screen.queryByText("Hosting invitations for 7")).toBeNull();
  expect(hosting.calls.every(enabled => !enabled)).toBe(true);
});

it("adds the Pricing page after Payments only while charges.pricing is on", () => {
  const { unmount } = mount();
  expect(navIds()).not.toContain("pricing");
  unmount();
  query.mockReturnValue({ data: { ...makerspace, enabled_features: ["charges.pricing"] }, isLoading: false, error: null, refetch: retry });
  mount({ path: `${BASE}/pricing` });
  expect(navIds().indexOf("pricing")).toBe(navIds().indexOf("money") + 1);
  expect(screen.getByText("Pricing editor")).toBeInTheDocument();
});

it("hides the settings pages of modules that are off instead of showing them empty (#183B)", () => {
  const bare = { ...makerspace, enabled_modules: ["staff_admin"] } as unknown as Makerspace;
  query.mockReturnValue({ data: bare, isLoading: false, error: null, refetch: retry });
  mount({ space: bare });
  for (const id of ["membership", "bookings", "materials"]) expect(navIds()).not.toContain(id);
  // Core pages stay.
  for (const id of ["general", "lending", "money", "notifications"]) expect(navIds()).toContain(id);
});

it("hides Inventory while the loans.enabled master is off (R4 audit B, #183B)", () => {
  const noLoans = { ...makerspace, enabled_features: [] } as unknown as Makerspace;
  query.mockReturnValue({ data: noLoans, isLoading: false, error: null, refetch: retry });
  mount({ space: noLoans });
  expect(navIds()).not.toContain("lending");
  expect(navIds()).toContain("general");
});

it("keeps the geofence under Membership when only presence is on", () => {
  const presenceOnly = { ...makerspace, enabled_modules: ["presence"] } as unknown as Makerspace;
  query.mockReturnValue({ data: presenceOnly, isLoading: false, error: null, refetch: retry });
  mount({ space: presenceOnly, path: `${BASE}/membership` });
  expect(navIds()).toContain("membership");
  expect(screen.getByText("Geofence editor")).toBeInTheDocument();
});
