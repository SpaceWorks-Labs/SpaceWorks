import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { MemberAccountPage } from "../members/MemberAccountPage";
import { MfaAccountPage } from "./MfaAccountPage";
import { setAccessToken } from "../../lib/api/sessionTokens";
import { setRouteSessionContext, type SessionContext } from "../../lib/api/sessionContext";
import type { SettingsLayoutProps, CenteredCardLayoutProps } from "../../components/layouts";

const state = vi.hoisted(() => ({ modules: [] as string[], bootstrapError: false }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual("../../lib/api"),
  refreshAccessToken: async () => true,
  bootstrapTenant: async () => {
    if (state.bootstrapError) throw new Error("Tenant unavailable");
    return { makerspace: { id: 1, slug: "venue", name: "Venue" }, modules: state.modules, features: [], branding: {} };
  },
}));
vi.mock("../../components/layouts", () => ({
  SettingsLayout: ({ sections, tabs }: SettingsLayoutProps) => <>
    {tabs?.map(tab => <a key={tab.key} href={tab.href}>{tab.label}</a>)}
    {sections.map(section => <div key={section.id}>{section.rows as ReactNode}</div>)}
  </>,
  CenteredCardLayout: ({ content, footer }: CenteredCardLayoutProps) => <>{content}{footer}</>,
}));
vi.mock("../members/MemberPortalTabs", () => ({ MemberPortalTabs: ({ children }: { children: ReactNode }) => children }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Member sign in</p> }));
vi.mock("../organizations/OrganizationSelfCreation", () => ({
  useOrganizationSelfCreationVisible: () => false, OrganizationSelfCreation: () => null,
}));
vi.mock("../../lib/tenant", () => ({ useOptionalTenant: () => ({ mode: "central" }) }));
// These settings never scan QR codes; keep the external WASM binary out of this unit test.
vi.mock("../../components/ui/QrScanner", () => ({ QrScanner: () => null }));

beforeEach(() => {
  state.modules = []; state.bootstrapError = false;
  setRouteSessionContext("person");
  setAccessToken(`header.${btoa(JSON.stringify({ user_id: 7, sid: "session-id", surface: "person" }))}.signature`, "person");
});

describe("account security without membership self-service", () => {
  it.each([false, true])("exposes logout-all with membership absent (bootstrap failure: %s)", async bootstrapError => {
    state.bootstrapError = bootstrapError;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const fetcher = vi.fn(async (_url: string, _options?: RequestInit) => new Response(JSON.stringify({ web_sessions: 1, devices: 0 }), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    render(<MemoryRouter initialEntries={["/m/venue/member/account?section=security"]}>
      <QueryClientProvider client={client}><Routes><Route path="/m/:slug/member/account" element={<MemberAccountPage />} /></Routes></QueryClientProvider>
    </MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Sign out everywhere" }));
    await screen.findByText("Member sign in");
    expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/auth\/logout-all$/), expect.objectContaining({ method: "POST" }));
    expect(fetcher.mock.calls.every(call => !String(call[0]).includes("/sessions"))).toBe(true);
    client.clear(); vi.unstubAllGlobals();
  });

  it.each<SessionContext>(["person", "person", "platform"])("exposes logout-all on %s account settings with MFA disabled", async context => {
    setRouteSessionContext(context);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ available: false, enabled: false, required: false }), { status: 200 })));
    render(<MemoryRouter><QueryClientProvider client={client}><MfaAccountPage /></QueryClientProvider></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Sign out everywhere" })).toBeEnabled();
    client.clear(); vi.unstubAllGlobals();
  });
});
