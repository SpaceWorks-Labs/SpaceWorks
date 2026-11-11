import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { authHeaders, clearAccessToken, getAccessToken, logout, refreshAccessToken, setAccessToken, staffFetch } from "./client";
import { consoleSessionHref, contextForRoute, setRouteSessionContext } from "./sessionContext";
import { onMfaEnrollmentRequired } from "./mfaEnrollment";
import { queryClientForContext } from "../queryClient";

vi.mock("../../features/staff/eventCheckInOfflineStore", () => ({ wipeOfflineScopes: vi.fn(async () => undefined) }));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
beforeEach(() => { setRouteSessionContext("person"); clearAccessToken("person"); clearAccessToken("platform"); vi.clearAllMocks(); });
afterEach(() => { clearAccessToken("person"); clearAccessToken("platform"); vi.unstubAllGlobals(); setRouteSessionContext("person"); });

it("routes collapse to person | platform: staff console, member area, kiosk and scanner share the person session", () => {
  for (const path of ["/m/forge/admin", "/admin/requests", "/m/forge/member", "/m/forge/scanner", "/kiosk/abc", "/guest-admin", "/mfa"]) {
    expect(contextForRoute(path)).toBe("person");
  }
  expect(contextForRoute("/admin", "?context=platform")).toBe("platform");
  expect(contextForRoute("/mfa", "?context=platform")).toBe("platform");
  expect(contextForRoute("/superadmin")).toBe("platform");
  expect(contextForRoute("/m/forge/admin", "?context=staff:forge")).toBe("person");
  expect(contextForRoute("/admin", "?surface=delegated")).toBe("person");
});

it("keeps the person and the platform account signed in independently", () => {
  setAccessToken("token:person", "person");
  setAccessToken("token:platform", "platform");
  expect(authHeaders("person")).toEqual({ Authorization: "Bearer token:person" });
  expect(getAccessToken("platform")).toBe("token:platform");
});

it("refresh sends only person or platform as the cookie context", async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => json({ access: `refreshed:${JSON.parse(options?.body as string).context}` }));
  vi.stubGlobal("fetch", fetcher);
  await Promise.all([refreshAccessToken("person"), refreshAccessToken("person"), refreshAccessToken("platform")]);
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls.map(([, options]) => JSON.parse(options?.body as string).context).sort()).toEqual(["person", "platform"]);
});

it("signing out the person clears only the person cache", async () => {
  setAccessToken("token:person", "person"); setAccessToken("token:platform", "platform");
  queryClientForContext("person").setQueryData(["private"], 1);
  queryClientForContext("platform").setQueryData(["private"], 2);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
  await logout("person");
  expect(getAccessToken("person")).toBe("");
  expect(getAccessToken("platform")).toBe("token:platform");
  expect(queryClientForContext("person").getQueryData(["private"])).toBeUndefined();
  expect(queryClientForContext("platform").getQueryData(["private"])).toBe(2);
});

it("console links keep the platform session explicit and leave person links alone", () => {
  expect(consoleSessionHref("/m/forge/admin/requests", "person")).toBe("/m/forge/admin/requests");
  expect(consoleSessionHref("/m/forge/admin/requests", "platform")).toBe("/admin/requests?context=platform");
});

it("an mfa_enrollment_required refusal notifies the console and never signs the person out", async () => {
  setAccessToken("token:person", "person");
  const heard = vi.fn();
  const stop = onMfaEnrollmentRequired(heard);
  vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Set up two-step sign-in.", code: "mfa_enrollment_required" }, 403)));
  const response = await staffFetch("/admin/makerspaces", {}, false, "person");
  expect(response.status).toBe(403);
  expect(heard).toHaveBeenCalledTimes(1);
  expect(getAccessToken("person")).toBe("token:person");
  stop();
});
