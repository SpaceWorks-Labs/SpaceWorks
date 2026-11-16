import { afterEach, describe, expect, it, vi } from "vitest";
import { beginGithubBrowser, beginOidcBrowser, completeOidcBrowserCallback, hasPendingSocialCallback, takeSocialReturnPath } from "./socialSdk";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ publicV1Request: request }));

describe("OIDC browser surface", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each(["member", "staff"] as const)("binds %s when starting the browser attempt", async (surface) => {
    window.history.replaceState(null, "", "/admin/assigned-events");
    request.mockResolvedValue({ state: "state", nonce: "nonce", authorization_url: "https://idp.example/authorize" });
    // Refuse storage to stop before the full-page redirect, after inspecting the real request.
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("disabled"); });
    await expect(beginOidcBrowser("campus", "", "", surface)).rejects.toThrow("Browser storage is required");
    expect(request).toHaveBeenLastCalledWith("/auth/social/oidc/campus/authorize", {
      method: "POST", body: JSON.stringify({ redirect_uri: `${window.location.origin}/admin/assigned-events`, surface }),
    });
  });
});

describe("sign-in next across the provider redirect (row 29)", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

  it("carries a same-origin next through the round trip and hands it back once", async () => {
    window.history.replaceState(null, "", `/m/forge/member?next=${encodeURIComponent("/m/forge/inventory?category=3")}`);
    request.mockResolvedValue({ state: "st-1", nonce: "n-1", authorization_url: "https://idp.example/authorize" });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    await beginOidcBrowser("campus", "", "forge");
    vi.unstubAllGlobals();
    expect(assign).toHaveBeenCalledWith("https://idp.example/authorize");
    // The redirect URI stays the bare page; next goes to the server and rides in session storage too.
    const startBody = JSON.parse(String(request.mock.calls.at(-1)?.[1]?.body));
    expect(startBody.redirect_uri).toBe(`${window.location.origin}/m/forge/member`);
    expect(startBody.next).toBe("/m/forge/inventory?category=3");

    window.history.replaceState(null, "", "/m/forge/member?code=c&state=st-1");
    expect(hasPendingSocialCallback()).toBe(true);
    request.mockResolvedValue({ access: "a", user: {}, outcome: "existing" });
    await completeOidcBrowserCallback();
    expect(hasPendingSocialCallback()).toBe(false);
    expect(takeSocialReturnPath()).toBe("/m/forge/inventory?category=3");
    expect(takeSocialReturnPath()).toBeUndefined();
  });

  it("drops an off-site next", async () => {
    window.history.replaceState(null, "", `/m/forge/member?next=${encodeURIComponent("https://evil.test/")}`);
    request.mockResolvedValue({ state: "st-2", nonce: "n-2", authorization_url: "https://idp.example/authorize" });
    vi.stubGlobal("location", { ...window.location, assign: vi.fn() });
    await beginOidcBrowser("campus", "", "forge");
    vi.unstubAllGlobals();
    expect(JSON.parse(String(request.mock.calls.at(-1)?.[1]?.body))).not.toHaveProperty("next");
    expect(window.sessionStorage.getItem("spaceworks.social.next.st-2")).toBeNull();
    window.sessionStorage.setItem("spaceworks.social.next", "//evil.test");
    expect(takeSocialReturnPath()).toBeUndefined();
  });

  it("sends next with the GitHub start and navigates to the callback's echoed next", async () => {
    window.history.replaceState(null, "", `/m/forge/member?next=${encodeURIComponent("/m/forge/loans")}`);
    request.mockResolvedValue({ state: "st-3", authorization_url: "https://github.example/authorize", expires_in: 600 });
    vi.stubGlobal("location", { ...window.location, assign: vi.fn() });
    await beginGithubBrowser();
    vi.unstubAllGlobals();
    expect(JSON.parse(String(request.mock.calls.at(-1)?.[1]?.body)).next).toBe("/m/forge/loans");

    window.history.replaceState(null, "", "/m/forge/member?code=c&state=st-3");
    request.mockResolvedValue({ access: "a", user: {}, outcome: "existing", next: "/m/forge/events?tab=mine" });
    await completeOidcBrowserCallback();
    expect(request).toHaveBeenLastCalledWith("/auth/social/github/callback", expect.objectContaining({ method: "POST" }));
    expect(takeSocialReturnPath()).toBe("/m/forge/events?tab=mine");
  });

  it("keeps the local next when the callback is an MFA challenge or echoes an off-site next", async () => {
    for (const [state, reply] of [["st-4", { mfa_required: true, enrollment_required: false, challenge: "c", expires_in: 300 }],
      ["st-5", { access: "a", user: {}, outcome: "existing", next: "//evil.test/x" }]] as const) {
      window.history.replaceState(null, "", `/m/forge/member?next=${encodeURIComponent("/m/forge/loans")}`);
      request.mockResolvedValue({ state, nonce: "n", authorization_url: "https://idp.example/authorize" });
      vi.stubGlobal("location", { ...window.location, assign: vi.fn() });
      await beginOidcBrowser("campus", "", "forge");
      vi.unstubAllGlobals();
      window.history.replaceState(null, "", `/m/forge/member?code=c&state=${state}`);
      request.mockResolvedValue(reply);
      await completeOidcBrowserCallback();
      expect(takeSocialReturnPath()).toBe("/m/forge/loans");
    }
  });
});
