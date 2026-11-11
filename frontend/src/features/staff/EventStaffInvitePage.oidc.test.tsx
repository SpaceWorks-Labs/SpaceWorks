import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EventStaffInvitePage } from "./EventStaffInvitePage";

const { publicRequest, request, me, refresh, beginOidc } = vi.hoisted(() => ({
  publicRequest: vi.fn(), request: vi.fn(), me: vi.fn(), refresh: vi.fn(), beginOidc: vi.fn(),
}));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  publicV1Request: publicRequest, staffRequest: request, fetchMe: me, refreshAccessToken: refresh,
}));
vi.mock("../auth/socialSdk", async () => ({
  ...await vi.importActual<typeof import("../auth/socialSdk")>("../auth/socialSdk"),
  beginOidcBrowser: beginOidc,
}));

const inviteKey = "spaceworks.eventStaffInvite";
function setup() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><EventStaffInvitePage /></MemoryRouter></QueryClientProvider>);
}
function config(accountsOff: boolean) {
  return {
    ...(accountsOff ? { member_accounts: { enabled: false }, password_login: { enabled: false } } : {}),
    social_auth: { "oidc:directory": { enabled: true, display_name: "Workshop directory", client_id: "directory", issuer: "https://directory.example" } },
  };
}

describe("OIDC event staff invitation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    window.history.replaceState(null, "", "/staff/event-invite#token=invite-secret");
    refresh.mockResolvedValue(false);
    me.mockResolvedValue({ username: "invitee", makerspaces: [] });
    request.mockResolvedValue({ id: 8, permissions: ["check_in"] });
    beginOidc.mockImplementation(async () => {
      expect(window.sessionStorage.getItem(inviteKey)).toBe("invite-secret");
      window.sessionStorage.setItem("spaceworks.oidc.nonce.return-state", "return-nonce");
    });
  });

  it.each([false, true])("retains the invitation through a redirect and consumes the callback with accounts off=%s", async (accountsOff) => {
    publicRequest.mockImplementation(async (path: string) => {
      if (path === "/config") return config(accountsOff);
      if (path === "/auth/social/oidc/callback") return { access: "oidc-access", user: {}, outcome: "existing" };
      throw new Error(`Unexpected request: ${path}`);
    });
    const original = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Continue with Workshop directory" }));
    await waitFor(() => expect(beginOidc).toHaveBeenCalledWith("directory", "", "", "member"));
    expect(window.location.hash).toBe("");
    if (accountsOff) expect(screen.queryByRole("button", { name: "Create a member account" })).not.toBeInTheDocument();
    original.unmount();

    // A full-page OIDC redirect remounts the page with no invitation fragment.
    window.history.replaceState(null, "", "/staff/event-invite?code=return-code&state=return-state&iss=directory");
    refresh.mockClear();
    refresh.mockResolvedValue(true); // An old cookie must not bypass the callback.
    setup();
    await screen.findByText("Signed in as invitee.");
    expect(publicRequest).toHaveBeenCalledWith("/auth/social/oidc/callback", {
      method: "POST", credentials: "include",
      body: JSON.stringify({ code: "return-code", state: "return-state", nonce: "return-nonce" }),
    });
    expect(refresh).not.toHaveBeenCalled();
    expect(window.location.search).toBe("");
    expect(window.sessionStorage.getItem("spaceworks.oidc.nonce.return-state")).toBeNull();
    expect(request).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Accept staff invitation" }));
    await screen.findByText(/Your event staff access is active/);
    expect(request).toHaveBeenCalledWith("/admin/event-staff-invites/redeem/", {
      method: "POST", body: JSON.stringify({ token: "invite-secret" }),
    });
    expect(window.sessionStorage.getItem(inviteKey)).toBeNull();
  });

  it("keeps the invitation available for retry after an OIDC refusal", async () => {
    window.sessionStorage.setItem(inviteKey, "invite-secret");
    window.history.replaceState(null, "", "/staff/event-invite?error=access_denied&state=return-state");
    publicRequest.mockResolvedValue(config(true));
    setup();
    await screen.findByRole("button", { name: "Continue with Workshop directory" });
    expect(screen.getByRole("alert")).toHaveTextContent("cancelled or refused");
    expect(window.location.search).toBe("");
    expect(window.sessionStorage.getItem(inviteKey)).toBe("invite-secret");
    expect(me).not.toHaveBeenCalled();
    expect(request).not.toHaveBeenCalled();
  });

  it("restores the pending invitation on an ordinary reload", async () => {
    window.sessionStorage.setItem(inviteKey, "old-invitation");
    window.history.replaceState(null, "", "/staff/event-invite");
    publicRequest.mockResolvedValue(config(true));
    setup();
    expect(await screen.findByRole("button", { name: "Continue with Workshop directory" })).toBeInTheDocument();
    expect(screen.queryByText(/missing its token/)).not.toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });
});
