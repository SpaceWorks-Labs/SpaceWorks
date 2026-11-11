import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MakerspaceSettingsPanel } from "../MakerspaceSettingsPanel";
import type { Makerspace } from "../StaffPanels";
const { query, retry } = vi.hoisted(() => ({ query: vi.fn(), retry: vi.fn() }));
vi.mock("../StaffPanels", () => ({ useStaffGet: query }));
vi.mock("../ApiClientsTelegramSettings", () => ({ ApiClientsTelegramSettings: () => null }));
vi.mock("../MakerspaceBrandingSettings", () => ({ MakerspaceBrandingSettings: () => null }));
vi.mock("../MakerspaceBookingRulesSettings", () => ({ MakerspaceBookingRulesSettings: () => null }));
vi.mock("../MakerspaceBookingSettings", () => ({ MakerspaceBookingSettings: () => null }));
vi.mock("../MakerspaceReminderSettings", () => ({ MakerspaceReminderSettings: () => null }));
vi.mock("../MakerspaceCustomDomainSettings", () => ({ MakerspaceCustomDomainSettings: () => null }));
vi.mock("../MakerspaceEmailSettings", () => ({ MakerspaceEmailSettings: () => null }));
vi.mock("../MakerspaceFilamentSettings", () => ({ MakerspaceFilamentSettings: () => null }));
vi.mock("../MakerspaceFeatureSettings", () => ({ MakerspaceFeatureSettings: () => null }));
vi.mock("../MakerspaceGeofenceSettings", () => ({ MakerspaceGeofenceSettings: () => <p>Geofence editor</p> }));
vi.mock("../../presence/PresencePrivacySettings", () => ({ PresencePrivacySettings: ({ makerspaceId, slug }: { makerspaceId: number; slug?: string }) => <p>Presence privacy editor {makerspaceId} {slug}</p> }));
// A draft the editor has not saved yet renders the shared SettingsActions bar.
vi.mock("../MakerspaceGeneralSettings", async () => {
  const { SettingsActions } = await import("../../../components/ui");
  return { MakerspaceGeneralSettings: () => <SettingsActions onDiscard={() => undefined} /> };
});
vi.mock("../IntegrationHealthPanel", () => ({ IntegrationHealthPanel: () => <p>Health checks</p> }));
vi.mock("../KioskStationSettings", () => ({ KioskStationSettings: () => null }));
vi.mock("../MakerspaceLocationSettings", () => ({ MakerspaceLocationSettings: () => null }));
vi.mock("../MakerspaceProfileSettings", () => ({ MakerspaceProfileSettings: () => null }));
vi.mock("../BillingDocumentsSettings", () => ({ BillingDocumentsSettings: () => null }));
vi.mock("../SpacePacksPanel", () => ({ SpacePacksPanel: () => null }));
vi.mock("../MakerspaceMembershipSettings", () => ({ MakerspaceMembershipSettings: () => null }));
vi.mock("../MakerspacePaymentSettings", () => ({ MakerspacePaymentSettings: () => <p>Payment settings</p> }));
vi.mock("../MakerspacePublicStatsSettings", () => ({ MakerspacePublicStatsSettings: () => null }));
vi.mock("../../stats/settings/PublicStatsSettingsPanel", () => ({ PublicStatsSettingsPanel: () => null }));
vi.mock("../MakerspaceSubdomainSettings", () => ({ MakerspaceSubdomainSettings: () => null }));
vi.mock("../MakerspaceWebhookSettings", () => ({ MakerspaceWebhookSettings: () => <p>Webhooks</p> }));
vi.mock("../MakerspaceArchiveRequestPanel", () => ({ MakerspaceArchiveRequestPanel: () => <p>Archive workflow</p> }));
vi.mock("../NotificationTimingSettings", () => ({ NotificationTimingSettings: () => null }));
vi.mock("../NotificationDestinations", () => ({ NotificationDestinations: () => null }));
vi.mock("../EvidenceRetentionPanel", () => ({ EvidenceRetentionPanel: () => null }));
vi.mock("../NotificationMuteMatrix", () => ({ NotificationMuteMatrix: () => null }));
vi.mock("../NotificationRecipientPicker", () => ({ NotificationRecipientPicker: () => null }));
vi.mock("../pricing/PricingSettings", () => ({ PricingSettings: () => <p>Pricing editor</p> }));
vi.mock("../SettingsAuthorityCard", () => ({ SettingsAuthorityCard: () => null }));
vi.mock("../../notifications/channelsApi", () => ({ useChannels: () => ({ data: undefined }) }));
const hosting = vi.hoisted(() => ({ available: false, calls: [] as boolean[] }));
vi.mock("../../hosting/hostingApi", () => ({ useHostingAvailability: (enabled = true) => { hosting.calls.push(enabled); return enabled && hosting.available; } }));
vi.mock("../HostingInvitations", () => ({ HostingInvitations: ({ scope }: { scope: { makerspaceId: number } }) => <p>Hosting invitations for {scope.makerspaceId}</p> }));
vi.mock("../MakerspaceLoanPolicySettings", () => ({ MakerspaceLoanPolicySettings: () => <p>Loan policy editor</p> }));
vi.mock("../../notifications/ChannelSetupPanel", () => ({ ChannelSetupPanel: () => <p>Channel setup</p> }));
vi.mock("../../notifications/ChannelDeliveryLog", () => ({ ChannelDeliveryLog: () => <p>Channel deliveries</p> }));

// Decision 246: which Settings pages exist per role (manager or not) and per module/capability switch (#183B).
const BASE = "/m/lab/admin/settings";
const ALL_MODULES = ["staff_admin", "membership", "presence", "bookings", "events", "machines", "printing", "notifications", "request_workflow"];
const ALL_FEATURES = ["loans.enabled", "charges.pricing"];
const space = (modules: string[], features: string[]) => ({ id: 7, name: "Community lab", slug: "lab", enabled_modules: modules, enabled_features: features }) as unknown as Makerspace;
beforeEach(() => { hosting.available = false; hosting.calls = []; retry.mockClear(); });

function pagesFor(modules: string[], features: string[], canManageMakerspace = true, isSuperadmin = false) {
  const makerspace = space(modules, features);
  query.mockReturnValue({ data: makerspace, isLoading: false, error: null, refetch: retry });
  const view = render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[`${BASE}/overview`]}>
    <MakerspaceSettingsPanel makerspace={makerspace} isSuperadmin={isSuperadmin} canManageMakerspace={canManageMakerspace} allowedTabs={[]} />
  </MemoryRouter></QueryClientProvider>);
  const ids = within(screen.getByRole("navigation", { name: "Settings pages" })).getAllByRole("link").map(link => link.getAttribute("href")!.replace(`${BASE}/`, ""));
  view.unmount();
  return ids;
}
const without = (list: string[], ...keys: string[]) => list.filter(key => !keys.includes(key));

describe("settings pages per role", () => {
  it("a manager with everything on sees every page", () => {
    expect(pagesFor(ALL_MODULES, ALL_FEATURES)).toEqual(expect.arrayContaining(["overview", "general", "branding", "public-page", "public-stats",
      "lending", "membership", "presence", "bookings", "events", "materials", "money", "pricing", "notifications", "channels", "integrations",
      "features", "health", "privacy"]));
  });

  it.each(["public-page", "presence", "events", "channels", "privacy", "hosting"])("%s needs manage_makerspace: a non-manager never gets it", id => {
    hosting.available = true;
    expect(pagesFor(ALL_MODULES, ALL_FEATURES, false)).not.toContain(id);
    expect(pagesFor(ALL_MODULES, ALL_FEATURES, true)).toContain(id);
  });

  it("keeps the always-on pages for a non-manager", () => {
    expect(pagesFor(ALL_MODULES, ALL_FEATURES, false)).toEqual(expect.arrayContaining(["general", "money", "notifications", "health", "lending"]));
  });
});

describe("settings pages with a module or capability off", () => {
  it.each([
    ["bookings", ["bookings"], []],
    ["events", ["events"], []],
    ["presence", ["presence"], []],
    ["materials", ["machines", "printing"], []],
    ["lending", [], ["loans.enabled"]],
    ["pricing", [], ["charges.pricing"]],
  ])("%s page disappears when %j / %j are off and stays when on", (page, modules, features) => {
    expect(pagesFor(ALL_MODULES, ALL_FEATURES)).toContain(page);
    expect(pagesFor(without(ALL_MODULES, ...modules), without(ALL_FEATURES, ...features))).not.toContain(page);
  });

  it("Membership survives while either membership or presence is on, and goes when both are off", () => {
    expect(pagesFor(without(ALL_MODULES, "membership"), ALL_FEATURES)).toContain("membership");
    expect(pagesFor(without(ALL_MODULES, "membership", "presence"), ALL_FEATURES)).not.toContain("membership");
  });

  it("the core pages stay with every optional module off", () => {
    expect(pagesFor(["staff_admin"], [])).toEqual(expect.arrayContaining(["overview", "general", "branding", "money", "notifications", "integrations", "health"]));
  });
});
