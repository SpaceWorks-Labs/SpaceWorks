/** 0.12.0 row 29: "Sign in to borrow" opens sign-in at once and returns the visitor to the inventory page. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { memberRequest, bootstrapTenant, refreshAccessToken } = vi.hoisted(() => ({
  memberRequest: vi.fn(), bootstrapTenant: vi.fn(), refreshAccessToken: vi.fn(),
}));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, memberRequest, bootstrapTenant, refreshAccessToken };
});
vi.mock("./MemberAuthPanel", () => ({ MemberAuthPanel: ({ onAuthenticated }: { onAuthenticated: () => void }) => <button onClick={onAuthenticated}>Complete sign in</button> }));

import { StructuredApiError } from "../../lib/api";
import { MemberArea } from "./MemberArea";

const assign = vi.fn();
const signedIn = (path: string) => Promise.resolve(path === "/memberships/me" ? { memberships: [], requests: [] }
  : path.includes("invitations") ? { invitations: [] } : []);
const replace = vi.fn();
function renderArea(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}>
    <Routes><Route path="/m/:slug/member" element={<MemberArea />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  for (const mock of [memberRequest, bootstrapTenant, refreshAccessToken, assign, replace]) mock.mockReset();
  window.sessionStorage.clear();
  refreshAccessToken.mockResolvedValue(undefined);
  bootstrapTenant.mockRejectedValue(new Error("offline"));
  memberRequest.mockImplementation((path: string) => path === "/memberships/me"
    ? Promise.reject(new StructuredApiError(401, { detail: "Sign in." })) : Promise.resolve([]));
  vi.stubGlobal("location", { ...window.location, assign, replace });
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("MemberArea sign-in return", () => {
  it("opens sign-in straight away and goes back to the inventory page afterwards", async () => {
    renderArea(`/m/forge/member?next=${encodeURIComponent("/m/forge/inventory?category=3")}`);
    fireEvent.click(await screen.findByRole("button", { name: "Complete sign in" }));
    expect(assign).toHaveBeenCalledWith("/m/forge/inventory?category=3");
  });

  it("ignores an off-site return address", async () => {
    renderArea(`/m/forge/member?next=${encodeURIComponent("https://evil.test/")}`);
    expect(await screen.findAllByRole("button", { name: "Sign in to your account" })).not.toHaveLength(0);
    expect(screen.queryByRole("button", { name: "Complete sign in" })).toBeNull();
  });

  it("sends a visitor who is already signed in straight to next", async () => {
    memberRequest.mockImplementation(signedIn);
    renderArea(`/m/forge/member?next=${encodeURIComponent("/m/forge/inventory?category=3")}`);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/m/forge/inventory?category=3"));
  });

  it("never follows an off-site next for a signed-in visitor", async () => {
    memberRequest.mockImplementation(signedIn);
    renderArea(`/m/forge/member?next=${encodeURIComponent("//evil.test/x")}`);
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/memberships/me"));
    expect(replace).not.toHaveBeenCalled();
  });

  it("returns to the next carried across an identity-provider redirect", async () => {
    window.sessionStorage.setItem("spaceworks.social.next", "/m/forge/inventory");
    renderArea("/m/forge/member");
    fireEvent.click((await screen.findAllByRole("button", { name: "Sign in to your account" }))[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Complete sign in" }));
    expect(assign).toHaveBeenCalledWith("/m/forge/inventory");
    expect(window.sessionStorage.getItem("spaceworks.social.next")).toBeNull();
  });
});
