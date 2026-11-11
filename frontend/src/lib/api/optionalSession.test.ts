import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cacheTenantPublishableKey, clearAccessToken, getAccessToken, setAccessToken } from "./client";
import { publicV1Request } from "./requests";
import { bootstrapTenant, tenantPublicRequest, tenantPublicRequestBlob } from "./tenant";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
beforeEach(() => {
  clearAccessToken();
  setAccessToken("optional-token");
  cacheTenantPublishableKey("optional-space", "explicit-space-key");
  cacheTenantPublishableKey("another-space", "ambient-other-key");
});
afterEach(() => { clearAccessToken(); vi.unstubAllGlobals(); });

// Every optional-auth JSON read shares these two entry points, including the
// status polls and the discovery/bootstrap reads that do not carry a tenant slug.
const publicReads = [
  "/discover/bookings/?page=1", "/discover/events/?page=1", "/config",
  "/public/organizations/community/", "/public/profiles/maker/",
  "/public/machine-service/3d-printer/requests/token/status",
];
it.each(publicReads)("public read %s recovers a refused optional session", async path => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    new Headers(options?.headers).get("Authorization") ? response({}, 403) : response({ visible: true }));
  vi.stubGlobal("fetch", fetcher);
  expect(await publicV1Request(path)).toEqual({ visible: true });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(getAccessToken()).toBe("optional-token");
});

const tenantReads = [
  "spaces/", "spaces/resource/availability", "events/", "events/event/", "events/event/website/",
  "inventory/item/", "machines/", "machine-types/1/intake", "membership-admission",
  "machine-service/3d-printer/queues", "machine-service/3d-printer/consumable-pools",
];
it.each(tenantReads)("tenant read %s preserves its explicit tenant key during fallback", async suffix => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => {
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("explicit-space-key");
    return headers.get("Authorization") ? response({}, 403) : response({ visible: true });
  });
  vi.stubGlobal("fetch", fetcher);
  expect(await tenantPublicRequest("optional-space", `/public/optional-space/${suffix}`)).toEqual({ visible: true });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("bootstrap discovery is anonymous from the start, so a session never costs a refused call", async () => {
  const bootstrap = { makerspace: { slug: "new-space" }, public_api: { publishable_key: "new-space-key" } };
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    new Headers(options?.headers).get("Authorization") ? response({}, 403) : response(bootstrap));
  vi.stubGlobal("fetch", fetcher);
  expect(await bootstrapTenant({ slug: "new-space" })).toEqual(bootstrap);
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it.each(["website/image", "events/event/calendar.ics"])("public blob %s refreshes then preserves the tenant key", async suffix => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) return response({ access: "fresh" });
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("explicit-space-key");
    return headers.get("Authorization") === "Bearer fresh" ? new Response("public bytes") : response({}, 401);
  });
  vi.stubGlobal("fetch", fetcher);
  expect(await (await tenantPublicRequestBlob("optional-space", `/public/optional-space/${suffix}`)).text()).toBe("public bytes");
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it.each([401, 403])("public blobs fall back anonymously after %s and preserve public refusals", async status => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) return response({}, 401);
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("explicit-space-key");
    return headers.get("Authorization") ? response({}, status) : response({}, 404);
  });
  vi.stubGlobal("fetch", fetcher);
  await expect(tenantPublicRequestBlob("optional-space", "/public/optional-space/website/image")).rejects.toMatchObject({ status: 404 });
  expect(fetcher).toHaveBeenCalledTimes(status === 401 ? 3 : 2);
});

it("public blobs remain readable when optional authentication is refused", async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    new Headers(options?.headers).get("Authorization") ? response({}, 403) : new Response("anonymous image bytes"));
  vi.stubGlobal("fetch", fetcher);
  expect(await (await tenantPublicRequestBlob("optional-space", "/public/optional-space/website/image")).text())
    .toBe("anonymous image bytes");
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it.each([404, 429, 500])("does not hide non-session errors (%s) with another request", async status => {
  const fetcher = vi.fn(async () => response({}, status));
  vi.stubGlobal("fetch", fetcher);
  await expect(publicV1Request("/public/profiles/maker/")).rejects.toMatchObject({ status });
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("does not retry network failures anonymously", async () => {
  const fetcher = vi.fn(async () => { throw new TypeError("Offline"); });
  vi.stubGlobal("fetch", fetcher);
  await expect(publicV1Request("/config")).rejects.toThrow("Offline");
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it.each(["POST", "PATCH", "DELETE"])("never retries a public %s mutation anonymously", async method => {
  const fetcher = vi.fn(async () => response({}, 403));
  vi.stubGlobal("fetch", fetcher);
  await expect(tenantPublicRequest("optional-space", "/public/optional-space/requests", { method }))
    .rejects.toMatchObject({ status: 403 });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
