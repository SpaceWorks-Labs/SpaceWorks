import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { staffRequest, memberRequest } = vi.hoisted(() => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest, memberRequest }));

import { reauthenticateMemberSocial, reauthenticateSocial } from "./reauthenticationSocial";

const STARTED = { authorization_url: "https://idp.example.org/auth", state: "S1", nonce: "N1", expires_in: 300 };
type Popup = { closed: boolean; close: ReturnType<typeof vi.fn>; location: { href: string; origin: string; pathname: string; search: string; hash: string } };
let popup: Popup;

function popupAt(over: Partial<Popup["location"]> = {}): Popup {
  return { closed: false, close: vi.fn(), location: { href: "", origin: window.location.origin, pathname: "/reauth/callback", search: "", hash: "", ...over } };
}

beforeEach(() => {
  vi.useFakeTimers();
  staffRequest.mockReset(); memberRequest.mockReset();
  popup = popupAt();
  vi.spyOn(window, "open").mockImplementation(() => popup as unknown as Window);
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

const settle = async (promise: Promise<unknown>) => { const out = promise.then(v => ({ ok: v }), e => ({ error: e as Error })); await vi.advanceTimersByTimeAsync(300); return out; };

describe("social re-authentication", () => {
  it("refuses with a clear message, and calls nothing, when the popup is blocked", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    await expect(reauthenticateSocial("github")).rejects.toThrow("Allow the identity-provider popup to verify this browser session.");
    expect(staffRequest).not.toHaveBeenCalled();
  });
  it("opens the popup synchronously with the reauth window name", () => {
    staffRequest.mockReturnValue(new Promise(() => undefined));
    void reauthenticateSocial("github");
    expect(window.open).toHaveBeenCalledWith("about:blank", "spaceworks-reauth", "popup,width=600,height=750");
  });
  it("starts with this origin's callback, sends the popup to the provider, then completes with the state, nonce and code", async () => {
    staffRequest.mockResolvedValueOnce(STARTED).mockResolvedValueOnce({ verified: true, expires_in: 300 });
    const run = reauthenticateSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    expect(staffRequest.mock.calls[0][0]).toBe("/auth/reauth/social/start");
    expect(JSON.parse(staffRequest.mock.calls[0][1].body)).toEqual({ provider: "github", redirect_uri: `${window.location.origin}/reauth/callback` });
    expect(popup.location.href).toBe(STARTED.authorization_url);
    popup.location.search = "?state=S1&code=abc";
    const result = await settle(run);
    expect(result).toEqual({ ok: { verified: true, expires_in: 300 } });
    expect(staffRequest.mock.calls[1][0]).toBe("/auth/reauth/social/complete");
    expect(JSON.parse(staffRequest.mock.calls[1][1].body)).toEqual({ state: "S1", nonce: "N1", code: "abc", id_token: "" });
    expect(popup.close).toHaveBeenCalledTimes(1);
  });
  it("reads an implicit-flow id_token from the fragment", async () => {
    staffRequest.mockResolvedValueOnce(STARTED).mockResolvedValueOnce({ verified: true, expires_in: 1 });
    const run = reauthenticateSocial("google");
    await vi.advanceTimersByTimeAsync(0);
    popup.location.hash = "#state=S1&id_token=tok";
    await settle(run);
    expect(JSON.parse(staffRequest.mock.calls[1][1].body)).toEqual({ state: "S1", nonce: "N1", code: "", id_token: "tok" });
  });
  it("rejects a callback whose state does not match, and never completes", async () => {
    staffRequest.mockResolvedValueOnce(STARTED);
    const run = reauthenticateSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    popup.location.search = "?state=EVIL&code=abc";
    const result = await settle(run);
    expect((result as { error: Error }).error.message).toBe("The identity provider refused verification.");
    expect(staffRequest).toHaveBeenCalledTimes(1);
    expect(popup.close).toHaveBeenCalled();
  });
  it.each([["a query error", { search: "?state=S1&error=access_denied" }], ["a fragment error", { hash: "#state=S1&error=access_denied" }]])("rejects %s from the provider", async (_n, over) => {
    staffRequest.mockResolvedValueOnce(STARTED);
    const run = reauthenticateSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    Object.assign(popup.location, over);
    expect(((await settle(run)) as { error: Error }).error.message).toBe("The identity provider refused verification.");
  });
  it("keeps waiting while the popup is still on the provider's origin, on another path, or has no state", async () => {
    staffRequest.mockResolvedValueOnce(STARTED).mockResolvedValueOnce({ verified: true, expires_in: 1 });
    const run = reauthenticateSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    popup.location.origin = "https://idp.example.org";
    await vi.advanceTimersByTimeAsync(500);
    popup.location.origin = window.location.origin; popup.location.pathname = "/elsewhere";
    await vi.advanceTimersByTimeAsync(500);
    popup.location.pathname = "/reauth/callback";
    await vi.advanceTimersByTimeAsync(500);
    expect(staffRequest).toHaveBeenCalledTimes(1);
    popup.location.search = "?state=S1&code=c";
    await settle(run);
    expect(staffRequest).toHaveBeenCalledTimes(2);
  });
  it("tolerates the cross-origin read error while the provider page is showing", async () => {
    staffRequest.mockResolvedValueOnce(STARTED).mockResolvedValueOnce({ verified: true, expires_in: 1 });
    const run = reauthenticateSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    const original = popup.location;
    Object.defineProperty(popup, "location", { configurable: true, get() { throw new DOMException("blocked", "SecurityError"); } });
    await vi.advanceTimersByTimeAsync(500);
    Object.defineProperty(popup, "location", { configurable: true, value: { ...original, search: "?state=S1&code=c" } });
    expect(await settle(run)).toMatchObject({ ok: { verified: true } });
  });
  it("reports a closed popup as cancelled", async () => {
    staffRequest.mockResolvedValueOnce(STARTED);
    const run = reauthenticateSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    popup.closed = true;
    expect(((await settle(run)) as { error: Error }).error.message).toBe("Identity verification was cancelled or expired.");
  });
  it("reports expiry after five minutes", async () => {
    staffRequest.mockResolvedValueOnce(STARTED);
    const run = reauthenticateSocial("github");
    const outcome = run.then(v => ({ ok: v }), e => ({ error: e as Error }));
    await vi.advanceTimersByTimeAsync(300_500);
    expect(((await outcome) as { error: Error }).error.message).toBe("Identity verification was cancelled or expired.");
  });
  it("closes the popup and rethrows when the start call fails", async () => {
    staffRequest.mockRejectedValueOnce(new Error("start failed"));
    await expect(reauthenticateSocial("github")).rejects.toThrow("start failed");
    expect(popup.close).toHaveBeenCalledTimes(1);
  });
  it("uses the member request client for member re-authentication", async () => {
    memberRequest.mockResolvedValueOnce(STARTED).mockResolvedValueOnce({ verified: true, expires_in: 1 });
    const run = reauthenticateMemberSocial("github");
    await vi.advanceTimersByTimeAsync(0);
    popup.location.search = "?state=S1&code=c";
    await settle(run);
    expect(memberRequest).toHaveBeenCalledTimes(2);
    expect(staffRequest).not.toHaveBeenCalled();
  });
});
