import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cacheTenantPublishableKey, clearAccessToken, getAccessToken, setAccessToken } from "../../lib/api";
import { presenceApi } from "./api";

const expired = "expired-presence-token";
const fresh = "fresh-presence-token";
const row = { display_name: "Maker", status: "visiting", since: "2026-10-17T10:00:00Z" };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

beforeEach(() => {
  clearAccessToken();
  cacheTenantPublishableKey("tv-space", "tv-space-key");
  setAccessToken(expired);
});
afterEach(() => { clearAccessToken(); vi.unstubAllGlobals(); });

it("refreshes an expired token so successive presence polls keep returning fresh rows", async () => {
  let polls = 0;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) return response({ access: fresh });
    expect(url).toContain("/public/makerspaces/tv-space/presence/now/");
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("tv-space-key");
    if (headers.get("Authorization") !== `Bearer ${fresh}`) return response({}, 401);
    return response([{ ...row, display_name: `Maker ${++polls}` }]);
  });
  vi.stubGlobal("fetch", fetcher);
  expect(await presenceApi.tv("tv-space")).toEqual([{ ...row, display_name: "Maker 1" }]);
  expect(await presenceApi.tv("tv-space")).toEqual([{ ...row, display_name: "Maker 2" }]);
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
});

it.each(["refused", "offline", "still_expired", "forbidden"])("polls anonymously when optional auth is %s", async failure => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      if (failure === "offline") throw new TypeError("Offline");
      return failure === "still_expired" ? response({ access: fresh }) : response({}, 401);
    }
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("tv-space-key");
    return headers.get("Authorization") ? response({}, failure === "forbidden" ? 403 : 401) : response([row]);
  });
  vi.stubGlobal("fetch", fetcher);
  expect(await presenceApi.tv("tv-space")).toEqual([row]);
  expect(await presenceApi.tv("tv-space")).toEqual([row]);
  if (failure === "forbidden") {
    expect(getAccessToken()).toBe(expired);
    expect(fetcher.mock.calls.some(([url]) => url.endsWith("/auth/refresh"))).toBe(false);
  }
});

it("keeps the public module/origin refusal authoritative after anonymous fallback", async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    new Headers(options?.headers).get("Authorization") ? response({}, 403) : response({ code: "module_disabled" }, 404));
  vi.stubGlobal("fetch", fetcher);
  await expect(presenceApi.tv("tv-space")).rejects.toMatchObject({ status: 404 });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("anonymous displays never attempt a session refresh", async () => {
  clearAccessToken();
  const fetcher = vi.fn(async () => response([row]));
  vi.stubGlobal("fetch", fetcher);
  expect(await presenceApi.tv("tv-space")).toEqual([row]);
  expect(fetcher).toHaveBeenCalledTimes(1);
});
