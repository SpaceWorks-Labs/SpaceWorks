import { expect, it, vi } from "vitest";
import { clearAccessToken, getSessionOwner, refreshAccessToken, setAccessToken } from "./sessionTokens";

vi.mock("../telemetry/sessionFence", () => ({ beforeSessionTransition: () => false, markSessionUnknown: vi.fn(), SessionNavigationInterrupted: class extends Error {} }));
vi.mock("../../features/staff/eventCheckInOfflineStore", () => ({ wipeOfflineScopes: vi.fn(async () => undefined) }));
vi.mock("./authFreeze", () => ({ freezeBeforeAuthMutation: vi.fn(), suspendPushForRefresh: vi.fn(async () => null), resumePushAfterRefresh: vi.fn(async () => undefined), queuePrivacyFreeze: vi.fn() }));
const token = (id: number, nonce: string) => `header.${btoa(JSON.stringify({ user_id: id, nonce }))}.signature`;

it("keeps the intake owner on same-owner rotation and clears it on identity loss or switch", () => {
  clearAccessToken("person");
  setAccessToken(token(1, "first"), "person");
  const first = getSessionOwner("person");
  setAccessToken(token(1, "rotation"), "person");
  expect(getSessionOwner("person")).toBe(first);
  setAccessToken(token(2, "switch"), "person");
  expect(getSessionOwner("person")).not.toBe(first);
  clearAccessToken("person");
  expect(getSessionOwner("person")).toBe("");
});

it("refuses a refresh that loses the known owner", async () => {
  clearAccessToken("person"); setAccessToken(token(1, "first"), "person");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ access: "malformed" }), { status: 200 })));
  expect(await refreshAccessToken("person")).toBe(false);
  expect(getSessionOwner("person")).toBe("");
  vi.unstubAllGlobals();
});

it("accepts same-owner refresh but refuses a different owner before replacing the session", async () => {
  clearAccessToken("person"); setAccessToken(token(1, "first"), "person");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ access: token(1, "rotated") }), { status: 200 })));
  expect(await refreshAccessToken("person")).toBe(true);
  expect(getSessionOwner("person")).toBe("1");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ access: token(2, "other") }), { status: 200 })));
  expect(await refreshAccessToken("person")).toBe(false);
  expect(getSessionOwner("person")).toBe("");
  vi.unstubAllGlobals();
});
