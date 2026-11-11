// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: written for string session contexts ("member", "staff:<slug>"); release SessionContext is "person" | "platform".
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { authHeaders, clearAccessToken, getAccessToken, logout, refreshAccessToken, setAccessToken, staffFetch } from "./client";
import { consoleSessionHref, contextForRoute, setRouteSessionContext } from "./sessionContext";
import { memberRequest, publicV1Request } from "./requests";
import { queryClientForContext } from "../queryClient";
import { offlineAccountScope } from "./sessionTokens";
import { requestReauthentication, setReauthenticationHandler } from "./reauthentication";

vi.mock("../../features/staff/eventCheckInOfflineStore", () => ({ wipeOfflineScopes: vi.fn(async () => undefined) }));
import { wipeOfflineScopes } from "../../features/staff/eventCheckInOfflineStore";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const contexts = ["member", "staff:forge", "staff:lab", "platform"] as const;
beforeEach(() => { setRouteSessionContext("member"); contexts.forEach(context => clearAccessToken(context)); vi.clearAllMocks(); });
afterEach(() => { contexts.forEach(context => clearAccessToken(context)); vi.unstubAllGlobals(); setRouteSessionContext("member"); });

it("keeps member, two staff tenants and platform signed in independently", () => {
  contexts.forEach(context => setAccessToken(`token:${context}`, context));
  contexts.forEach(context => expect(authHeaders(context)).toEqual({ Authorization: `Bearer token:${context}` }));
  expect(getAccessToken("member")).toBe("token:member");
});

it("deduplicates refresh only within a context and sends the explicit cookie context", async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => {
    const { context } = JSON.parse(options?.body as string);
    return json({ access: `refreshed:${context}` });
  });
  vi.stubGlobal("fetch", fetcher);
  await Promise.all([refreshAccessToken("member"), refreshAccessToken("member"), refreshAccessToken("staff:forge"), refreshAccessToken("platform")]);
  expect(fetcher).toHaveBeenCalledTimes(3);
  for (const context of ["member", "staff:forge", "platform"] as const) expect(getAccessToken(context)).toBe(`refreshed:${context}`);
  expect(fetcher.mock.calls.every(([, options]) => options?.credentials === "include")).toBe(true);
});

it("signs out one context and clears only its queries and offline scope", async () => {
  contexts.forEach(context => setAccessToken(`token:${context}`, context));
  contexts.forEach(context => queryClientForContext(context).setQueryData(["private"], context));
  vi.mocked(wipeOfflineScopes).mockClear();
  const fetcher = vi.fn(async () => new Response(null, { status: 204 })); vi.stubGlobal("fetch", fetcher);
  await logout("staff:forge");
  expect(JSON.parse((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)).toEqual({ context: "staff:forge" });
  expect(getAccessToken("staff:forge")).toBe("");
  expect(queryClientForContext("staff:forge").getQueryData(["private"])).toBeUndefined();
  for (const context of ["member", "staff:lab", "platform"] as const) {
    expect(getAccessToken(context)).toBe(`token:${context}`);
    expect(queryClientForContext(context).getQueryData(["private"])).toBe(context);
  }
  expect(wipeOfflineScopes).toHaveBeenCalledExactlyOnceWith("session:staff:forge:");
});

it.each(["logout", "new login"])("rejects a stale refresh after %s without replacing newer credentials", async action => {
  let finish!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn((url: string) => url.endsWith("refresh")
    ? new Promise<Response>(resolve => { finish = resolve; }) : Promise.resolve(new Response(null, { status: 204 }))));
  const refresh = refreshAccessToken("staff:forge");
  if (action === "logout") await logout("staff:forge"); else setAccessToken("new-login", "staff:forge");
  finish(json({ access: "stale" }));
  expect(await refresh).toBe(false);
  expect(getAccessToken("staff:forge")).toBe(action === "logout" ? "" : "new-login");
});

it("binds refresh/retry to its original context when navigation changes", async () => {
  setAccessToken("old-staff", "staff:forge"); setAccessToken("member", "member");
  setRouteSessionContext("staff:forge");
  const headers: (string | null)[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("refresh")) { expect(JSON.parse(options?.body as string)).toEqual({ context: "staff:forge" }); setRouteSessionContext("member"); return json({ access: "fresh-staff" }); }
    headers.push(new Headers(options?.headers).get("Authorization"));
    return json({}, headers.length === 1 ? 401 : 200);
  }));
  await expect(staffFetch("/admin/test")).rejects.toMatchObject({ name: "AbortError" });
  expect(headers).toEqual(["Bearer old-staff", "Bearer fresh-staff"]);
  expect(getAccessToken("member")).toBe("member");
});

it.each(["navigation", "account change"])("discards a pending mutation's private result after %s", async change => {
  setRouteSessionContext("staff:forge"); setAccessToken("original", "staff:forge");
  let finish!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
  const pending = staffFetch("/admin/private-mutation", { method: "POST", body: "{}" });
  if (change === "navigation") setRouteSessionContext("member"); else setAccessToken("different-account", "staff:forge");
  finish(json({ title: "Private staff data" }));
  await expect(pending).rejects.toMatchObject({ name: "AbortError" });
});

it("public and member requests never borrow the active staff token", async () => {
  setRouteSessionContext("staff:forge"); setAccessToken("staff", "staff:forge"); setAccessToken("member", "member");
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => {
    expect(new Headers(options?.headers).get("Authorization")).toBe("Bearer member"); return json({});
  }); vi.stubGlobal("fetch", fetcher);
  await memberRequest("/auth/me"); await publicV1Request("/public/catalogue");
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("does not let an old refresh finalizer release a newer refresh's lock", async () => {
  const responses: ((value: Response) => void)[] = [];
  const fetcher = vi.fn(() => new Promise<Response>(resolve => { responses.push(resolve); }));
  vi.stubGlobal("fetch", fetcher);
  const old = refreshAccessToken("staff:forge");
  clearAccessToken("staff:forge");
  const fresh = refreshAccessToken("staff:forge");
  responses[0](json({ access: "old" })); expect(await old).toBe(false);
  expect(refreshAccessToken("staff:forge")).toBe(fresh);
  expect(fetcher).toHaveBeenCalledTimes(2);
  responses[1](json({ access: "new" })); expect(await fresh).toBe(true);
});

it("partitions offline rosters by browser identity as well as context", () => {
  const token = (id: number) => `header.${btoa(JSON.stringify({ user_id: id, sid: `session-${id}`, surface: "staff" }))}.signature`;
  setAccessToken(token(1), "staff:forge"); const first = offlineAccountScope("staff:event", "staff:forge");
  setAccessToken(token(2), "staff:forge"); const second = offlineAccountScope("staff:event", "staff:forge");
  expect(first).not.toBe(second); expect(first).toMatch(/^session:staff:forge:/);
  expect(offlineAccountScope("staff:event", "member")).not.toBe(second);
});

it("refuses to refresh an old account into another tab's replacement account", async () => {
  const token = (user_id: number) => `header.${btoa(JSON.stringify({ user_id }))}.signature`;
  setAccessToken(token(1), "staff:forge"); setAccessToken("member", "member");
  queryClientForContext("staff:forge").setQueryData(["private"], "old staff data");
  vi.stubGlobal("fetch", vi.fn(async () => json({ access: token(2) })));
  expect(await refreshAccessToken("staff:forge")).toBe(false);
  expect(getAccessToken("staff:forge")).toBe(""); expect(getAccessToken("member")).toBe("member");
  expect(queryClientForContext("staff:forge").getQueryData(["private"])).toBeUndefined();
});

it("shares reauthentication only within the initiating context", async () => {
  let finish!: (value: boolean) => void;
  const member = vi.fn(async () => true);
  const staff = vi.fn(() => new Promise<boolean>(resolve => { finish = resolve; }));
  const removeMember = setReauthenticationHandler(member, "member");
  const removeStaff = setReauthenticationHandler(staff, "staff:forge");
  const first = requestReauthentication("staff:forge"); const second = requestReauthentication("staff:forge");
  expect(await requestReauthentication("member")).toBe(true); expect(member).toHaveBeenCalledOnce();
  expect(staff).toHaveBeenCalledOnce(); finish(true); expect(await Promise.all([first, second])).toEqual([true, true]);
  removeMember(); removeStaff();
});

it.each([
  ["/m/forge/admin/inventory", "", "", "staff:forge"], ["/admin/inventory", "", "forge", "staff:forge"],
  ["/admin/assigned-events", "", "forge", "member"], ["/admin/organizations", "", "", "member"],
  ["/m/forge/admin/inventory", "?surface=delegated", "", "member"],
  ["/admin/users", "?context=platform", "", "platform"], ["/m/forge/member", "", "", "member"],
  ["/m/forge", "", "", "member"], ["/mfa", "?context=staff%3Aforge", "", "staff:forge"],
  ["/m/forge/kiosk/token", "", "", "staff:forge"], ["/kiosk/token", "", "forge", "staff:forge"],
  ["/m/forge/scanner", "?context=staff%3Aother", "", "staff:forge"],
  ["/scanner", "?context=staff%3Aforge", "", "staff:forge"], ["/scanner", "", "forge", "staff:forge"],
  ["/scanner/", "?context=staff%3Aother", "forge", "staff:forge"],
  ["/m/forge/kiosk/token/", "?surface=delegated&context=platform", "", "staff:forge"],
  ["/kiosk/token", "?context=staff%3Aforge", "", "staff:forge"],
  ["/kiosk/forge", "", "", "member"], ["/m/forge/event-check-in/token", "", "", "member"],
  ["/staff/event-invite", "", "forge", "member"], ["/staff/booking-invite", "", "forge", "member"],
  ["/staff-invitations/accept", "", "forge", "member"], ["/m/forge/guest-admin", "", "", "staff:forge"],
])("resolves %s %s to the intended session", (path, search, tenant, expected) => {
  expect(contextForRoute(path, search, tenant)).toBe(expected);
});

it("keeps filters and delegated context together, and platform links on platform routes", () => {
  const delegated = consoleSessionHref("/m/forge/admin/machines?machine=9&detail_tab=Maintenance", "member");
  const params = new URL(delegated, window.location.origin).searchParams;
  expect(params.get("machine")).toBe("9"); expect(params.get("detail_tab")).toBe("Maintenance");
  expect(params.get("surface")).toBe("delegated");
  expect(contextForRoute(delegated.split("?")[0], "?" + params)).toBe("member");
  expect(consoleSessionHref("/m/forge/admin/users", "platform")).toBe("/admin/users?context=platform");
});
