import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { staffRequest, publicV1Request } = vi.hoisted(() => ({ staffRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<object>("../../lib/api")), staffRequest, publicV1Request }));
vi.mock("./socialSdk", async () => ({ ...(await vi.importActual<object>("./socialSdk")), loadScript: vi.fn().mockResolvedValue(undefined) }));

import { LinkedSignInList } from "./LinkedSignInList";

let googleCallback: ((value: { credential?: string }) => Promise<void>) | undefined;
const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
  <LinkedSignInList /></QueryClientProvider>);
const config = (social_auth: object) => publicV1Request.mockImplementation(async (path: string) => {
  if (path === "/config") return { social_auth };
  if (path === "/auth/social/nonce") return { nonce: "n-1" };
  throw new Error(`Unexpected ${path}`);
});

beforeEach(() => {
  staffRequest.mockReset(); publicV1Request.mockReset(); googleCallback = undefined;
  window.google = { accounts: { id: {
    initialize: (options: Record<string, unknown>) => { googleCallback = options.callback as typeof googleCallback; },
    renderButton: vi.fn(),
  } } };
});
afterEach(() => { delete window.google; });

it("links Google with a member web nonce and refreshes the list", async () => {
  config({ google: { enabled: true, web_client_id: "client-1" }, apple: { enabled: false, service_id: "" } });
  let linked = false;
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === "/auth/social/providers" && init?.method === "POST") { linked = true; return { provider: "google", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" }; }
    return linked ? [{ provider: "google", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" }] : [];
  });
  show();
  expect(screen.queryByRole("button", { name: "Link Apple" })).toBeNull();
  fireEvent.click(await screen.findByRole("button", { name: "Link Google" }));
  await waitFor(() => expect(googleCallback).toBeDefined());
  expect(JSON.parse(publicV1Request.mock.calls.find(([path]) => path === "/auth/social/nonce")![1].body))
    .toEqual({ provider: "google", surface: "member", delivery: "web", client_platform: "web" });
  await act(async () => { await googleCallback!({ credential: "id-token" }); });
  const post = staffRequest.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(JSON.parse(post[1].body)).toEqual({ provider: "google", id_token: "id-token", nonce: "n-1", client_platform: "web" });
  expect(await screen.findByText("Google is now linked.")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Unlink Google" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Link Google" })).toBeNull();
});

it("offers nothing when no browser provider is configured", async () => {
  config({ github: false });
  staffRequest.mockResolvedValue([]);
  show();
  expect(await screen.findByText("No sign-in accounts are linked.")).toBeInTheDocument();
  await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
  expect(screen.queryByRole("region", { name: "Link another sign-in" })).toBeNull();
});

describe("redirect providers (GitHub, OIDC)", () => {
  const assign = vi.fn();
  const original = window.location;
  beforeEach(() => {
    sessionStorage.clear(); assign.mockReset();
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, origin: "https://lab.example",
      pathname: "/member/account", search: "", href: "https://lab.example/member/account", assign } });
  });
  afterEach(() => { Object.defineProperty(window, "location", { configurable: true, value: original }); });

  it("starts a session-bound GitHub link and keeps the nonce in this tab", async () => {
    config({ github: true, "oidc:campus": { enabled: true, display_name: "Campus SSO", client_id: "c", issuer: "https://idp" } });
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/auth/social/github/link/authorize") return { authorization_url: "https://github.com/login/oauth/authorize?x", state: "s-1", expires_in: 600 };
      return [];
    });
    show();
    expect(await screen.findByRole("button", { name: "Link Campus SSO" })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Link GitHub" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://github.com/login/oauth/authorize?x"));
    const body = JSON.parse(staffRequest.mock.calls.find(([path]) => path === "/auth/social/github/link/authorize")![1].body);
    expect(body.redirect_uri).toBe("https://lab.example/member/account");
    expect(sessionStorage.getItem("spaceworks.social-link.nonce.s-1")).toBe(body.nonce);
  });

  it("starts an OIDC link with the server nonce", async () => {
    config({ "oidc:campus": { enabled: true, display_name: "Campus SSO", client_id: "c", issuer: "https://idp" } });
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/auth/social/oidc/campus/link/authorize") return { authorization_url: "https://idp/authorize?y", state: "s-2", nonce: "server-nonce", expires_in: 600 };
      return [];
    });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Link Campus SSO" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://idp/authorize?y"));
    expect(JSON.parse(staffRequest.mock.calls.find(([path]) => path === "/auth/social/oidc/campus/link/authorize")![1].body))
      .toEqual({ redirect_uri: "https://lab.example/member/account" });
    expect(sessionStorage.getItem("spaceworks.social-link.nonce.s-2")).toBe("server-nonce");
  });

  it("finishes the link when the provider returns to this page, once", async () => {
    sessionStorage.setItem("spaceworks.social-link.nonce.s-3", "n-3");
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, origin: "https://lab.example",
      pathname: "/member/account", search: "?code=c-3&state=s-3", href: "https://lab.example/member/account?code=c-3&state=s-3", assign } });
    const replace = vi.spyOn(window.history, "replaceState").mockImplementation(() => undefined);
    config({ github: true });
    let linked = false;
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/auth/social/link/callback") { linked = true; return { provider: "github", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" }; }
      return linked ? [{ provider: "github", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" }] : [];
    });
    show();
    expect(await screen.findByText("GitHub is now linked.")).toBeInTheDocument();
    const calls = staffRequest.mock.calls.filter(([path]) => path === "/auth/social/link/callback");
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0][1].body)).toEqual({ code: "c-3", state: "s-3", nonce: "n-3" });
    expect(sessionStorage.getItem("spaceworks.social-link.nonce.s-3")).toBeNull();
    expect(replace).toHaveBeenCalledWith({}, "", "/member/account");
    replace.mockRestore();
  });

  it("ignores a provider return it did not start (no stored nonce)", async () => {
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, origin: "https://lab.example",
      pathname: "/member/account", search: "?code=c&state=other", href: "https://lab.example/member/account?code=c&state=other", assign } });
    config({ github: true });
    staffRequest.mockResolvedValue([]);
    show();
    expect(await screen.findByRole("button", { name: "Link GitHub" })).toBeInTheDocument();
    expect(staffRequest.mock.calls.some(([path]) => path === "/auth/social/link/callback")).toBe(false);
  });
});
