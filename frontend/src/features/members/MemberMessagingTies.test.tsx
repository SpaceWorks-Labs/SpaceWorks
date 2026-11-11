import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemberArea } from "./MemberArea";
import { memberMessaging } from "../../test/messagingFixtures";
import { bootstrapTenant, memberRequest, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { channelKeys } from "../notifications/channelsApi";

vi.mock("../../lib/api", async importOriginal => ({
  ...await importOriginal<typeof import("../../lib/api")>(),
  bootstrapTenant: vi.fn(), memberRequest: vi.fn(), refreshAccessToken: vi.fn(),
}));
vi.mock("../../lib/useTenantBranding", () => ({ useTenantBranding: () => ({}) }));
vi.mock("./memberCard/offlineCard", () => ({ forgetOfflineMemberData: vi.fn() }));
vi.mock("./MemberClaimSession", () => ({ hasClaimSession: () => false, MemberClaimSession: () => null }));

function mount(section = "channels", client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/m/tied/member/account-portal?section=${section}`]}>
    <Routes><Route path="/m/:slug/member/account-portal" element={<MemberArea />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
  return client;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(refreshAccessToken).mockResolvedValue(true);
  vi.mocked(bootstrapTenant).mockResolvedValue({
    makerspace: { id: 41, slug: "tied", name: "Tied lab", membership_policy: "open",
      public_code: "tied", location: "", geofence_enabled: false },
    frontend: { type: "shared", hostname: "localhost", allowed_origins: [] },
    modules: [], features: [], workflows: [], theme: {}, branding: {}, email_enabled: false,
    public_api: { base_url: "", publishable_key: "", inventory_path: "" },
  });
  const respond = async (path: string, options?: RequestInit) => {
    if (path === "/memberships/me") return { memberships: [], requests: [] };
    if (path === "/auth/me") return { username: "borrower", email_verified: true };
    if (path === "/memberships/invitations") return { invitations: [] };
    if (path === "/me/messaging/consent") {
      const body = JSON.parse(String(options?.body));
      return { ...memberMessaging, [body.channel]: { ...memberMessaging[body.channel as "sms" | "whatsapp"], consented: body.action === "opted_in" } };
    }
    if (path === "/integrations/makerspace/41/personal/preferences") return { preferences: [
      { category: "bookings", channels: ["email"], email_fallback: true, available_channels: ["email", "sms", "whatsapp"] },
    ] };
    if (path.endsWith("/personal/endpoints") || path.includes("/personal/deliveries")) return { count: 0, results: [], next: null, previous: null };
    if (path === "/me/messaging?makerspace=41") return memberMessaging;
    return [];
  };
  vi.mocked(memberRequest).mockImplementation(respond as typeof memberRequest);
});

describe("account-only messaging admission", () => {
  it("shows Channels and permits sender-bound SMS consent with no membership or membership module", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "SMS notifications" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Allow SMS notifications" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/me/messaging/consent", {
      method: "POST", body: JSON.stringify({ makerspace: 41, channel: "sms", action: "opted_in" }),
    }));
  });

  it("allows account-only owners to reach phone verification", async () => {
    mount("phone");
    expect(await screen.findByRole("heading", { name: "Verify your phone" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Phone number (E.164)" })).toBeInTheDocument();
  });

  it("hides the section after the API refuses a refreshed tie, including cached data", async () => {
    const client = mount();
    expect(await screen.findByRole("heading", { name: "SMS notifications" })).toBeInTheDocument();
    const original = vi.mocked(memberRequest).getMockImplementation()!;
    vi.mocked(memberRequest).mockImplementation(async (path, options) => {
      if (path === "/integrations/makerspace/41/personal/preferences") throw new StructuredApiError(404, { detail: "Not found." });
      return original(path, options);
    });
    await client.invalidateQueries({ queryKey: channelKeys.preferences(41) });
    await waitFor(() => expect(screen.queryByRole("heading", { name: "SMS notifications" })).not.toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Channels" })).not.toBeInTheDocument();
  });
});

it("does not offer notification settings to a locally revoked member despite historical ties", async () => {
  const original = vi.mocked(memberRequest).getMockImplementation()!;
  vi.mocked(memberRequest).mockImplementation(async (path, options) => path === "/memberships/me"
    ? { memberships: [{ makerspace: { slug: "tied", name: "Tied lab" }, membership_status: "revoked", role: "member" }], requests: [] }
    : original(path, options));
  mount();
  await screen.findByRole("link", { name: "Invitations" });
  expect(screen.queryByRole("link", { name: "Channels" })).toBeNull();
  expect(screen.queryByLabelText("Allow SMS notifications")).toBeNull();
  expect(vi.mocked(memberRequest).mock.calls.some(([path]) => path.includes("/personal/preferences"))).toBe(false);
});
