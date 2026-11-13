import { QueryObserver } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearAccessToken, getAccessToken, logout, setAccessToken, staffFetch } from "./client";
import { memberRequest } from "./requests";
import { StructuredApiError } from "./errors";
import { setRouteSessionContext } from "./sessionContext";
import { queryClientForContext } from "../queryClient";

vi.mock("../../features/staff/eventCheckInOfflineStore", () => ({ wipeOfflineScopes: vi.fn(async () => undefined) }));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const access = `e30.${btoa(JSON.stringify({ user_id: 7 }))}.signature`;
beforeEach(() => { setRouteSessionContext("person"); clearAccessToken("person"); clearAccessToken("platform"); });
afterEach(() => { clearAccessToken("person"); clearAccessToken("platform"); vi.unstubAllGlobals(); });

it("settles an anonymous membership query as 401 instead of stranding its observer loading", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Not authenticated." }, 401)));
  const client = queryClientForContext("person");
  const observer = new QueryObserver(client, { queryKey: ["member", "memberships"],
    queryFn: () => memberRequest("/memberships/me"), retry: false });
  const unsubscribe = observer.subscribe(() => {});
  try {
    await vi.waitFor(() => expect(observer.getCurrentResult().status).toBe("error"));
    const result = observer.getCurrentResult();
    expect(result.isLoading).toBe(false);
    expect(result.error).toBeInstanceOf(StructuredApiError);
    expect((result.error as StructuredApiError).status).toBe(401);
    expect(client.getQueryCache().find({ queryKey: ["member", "memberships"] })).toBeDefined();
  } finally { unsubscribe(); }
});

it("still clears the real expired person's protected cache and leaves the platform alone", async () => {
  setAccessToken(access, "person");
  queryClientForContext("person").setQueryData(["private"], "person secret");
  queryClientForContext("platform").setQueryData(["private"], "platform secret");
  vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Expired." }, 401)));
  expect((await staffFetch("/memberships/me", {}, true, "person")).status).toBe(401);
  expect(getAccessToken("person")).toBe("");
  expect(queryClientForContext("person").getQueryData(["private"])).toBeUndefined();
  expect(queryClientForContext("platform").getQueryData(["private"])).toBe("platform secret");
});

it.each([200, 401])("retains cookie refresh with no initial access JWT and handles its retried %i", async status => {
  const client = queryClientForContext("person");
  client.setQueryData(["private"], "cookie session data");
  let reads = 0;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      expect(options?.credentials).toBe("include");
      return json({ access });
    }
    reads++;
    return json({}, reads === 1 ? 401 : status);
  });
  vi.stubGlobal("fetch", fetcher);
  expect((await staffFetch("/memberships/me", {}, true, "person")).status).toBe(status);
  expect(reads).toBe(2);
  expect(getAccessToken("person")).toBe(status === 200 ? access : "");
  expect(client.getQueryData(["private"])).toBe(status === 200 ? "cookie session data" : undefined);
});

it("explicit logout still clears private cache even with no current access JWT", async () => {
  queryClientForContext("person").setQueryData(["private"], "retained data");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
  await logout("person");
  expect(queryClientForContext("person").getQueryData(["private"])).toBeUndefined();
});

it.each(["account_restricted", "account_suspended"])("keeps a %s session usable for its own charges", async code => {
  setAccessToken(access, "person");
  const fetcher = vi.fn(async (url: string) => url.endsWith("/payments")
    ? json([{ id: 4 }]) : json({ detail: "Limited account", code }, 401));
  vi.stubGlobal("fetch", fetcher);
  await expect(memberRequest("/memberships/me")).rejects.toMatchObject({ status: 401, code });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(getAccessToken("person")).toBe(access);
  await expect(memberRequest("/member/makerspaces/1/payments")).resolves.toEqual([{ id: 4 }]);
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/auth/refresh"))).toBe(false);
});
