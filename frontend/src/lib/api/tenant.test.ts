import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cacheTenantPublishableKey, clearAccessToken, setAccessToken, setRuntimePublishableKey } from "./client";
import { bootstrapTenant, tenantMemberRequest } from "./tenant";
import { publicV1Request } from "./requests";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

describe("tenant authenticated requests", () => {
  beforeEach(() => { setAccessToken("old-access"); setRuntimePublishableKey(""); });
  afterEach(() => { vi.unstubAllGlobals(); clearAccessToken(); setRuntimePublishableKey(""); });

  it("bootstraps an uncached tenant and carries its key with request options", async () => {
    const request = vi.fn(async (url: string) => url.includes("/bootstrap?")
      ? json({ makerspace: { slug: "new-venue" }, public_api: { publishable_key: "pk-new" } })
      : json({ eligible: true }));
    vi.stubGlobal("fetch", request);
    await expect(tenantMemberRequest(" new-venue ", "/public/new-venue/events/one/eligibility/", {
      cache: "no-store", headers: { "X-Request-Test": "kept" },
    })).resolves.toEqual({ eligible: true });
    expect(request.mock.calls[0][0]).toContain("/bootstrap?slug=new-venue");
    const [, options] = vi.mocked(fetch).mock.calls[1];
    expect(options?.cache).toBe("no-store");
    const headers = new Headers(options?.headers);
    expect(headers.get("X-Publishable-Key")).toBe("pk-new");
    expect(headers.get("Authorization")).toBe("Bearer old-access");
    expect(headers.get("X-Request-Test")).toBe("kept");
  });

  it("bootstraps anonymously even with a member session, so no staff-route 403 is spent", async () => {
    const request = vi.fn(async (_url: string, _options?: RequestInit) => json({ makerspace: { slug: "venue" }, public_api: { publishable_key: "pk-venue" } }));
    vi.stubGlobal("fetch", request);
    await bootstrapTenant({ slug: "venue" });
    expect(request).toHaveBeenCalledTimes(1);
    expect(new Headers(request.mock.calls[0][1]?.headers).get("Authorization") ?? "").toBe("");
  });

  it("keeps the requested tenant key on retry when another tenant is active", async () => {
    cacheTenantPublishableKey("venue", "pk-venue");
    cacheTenantPublishableKey("other", "pk-other");
    setRuntimePublishableKey("pk-runtime");
    const request = vi.fn()
      .mockResolvedValueOnce(json({ detail: "Token expired" }, 401))
      .mockResolvedValueOnce(json({ access: "new-access" }))
      .mockResolvedValueOnce(json({ eligible: true }));
    vi.stubGlobal("fetch", request);
    await expect(tenantMemberRequest("venue", "/public/venue/events/one/eligibility/"))
      .resolves.toEqual({ eligible: true });
    expect(request).toHaveBeenCalledTimes(3);
    const first = new Headers(request.mock.calls[0][1].headers);
    const retry = new Headers(request.mock.calls[2][1].headers);
    expect(first.get("Authorization")).toBe("Bearer old-access");
    expect(retry.get("Authorization")).toBe("Bearer new-access");
    expect(first.get("X-Publishable-Key")).toBe("pk-venue");
    expect(retry.get("X-Publishable-Key")).toBe("pk-venue");
    expect(request.mock.calls[1]).toEqual([expect.stringMatching(/\/auth\/refresh$/), {
      method: "POST", credentials: "include", headers: { "X-Refresh-CSRF": "1", "Content-Type": "application/json" }, body: JSON.stringify({ context: "person" }),
    }]);
  });

  it("can discover another tenant's key without switching the current public page's tenant", async () => {
    cacheTenantPublishableKey("current-profile", "pk-current");
    const request = vi.fn(async (url: string) => url.includes("/bootstrap?")
      ? json({ makerspace: { slug: "discovered" }, public_api: { publishable_key: "pk-discovered" } })
      : json({ handle: "maker.one" }));
    vi.stubGlobal("fetch", request);
    await bootstrapTenant({ slug: "discovered" }, { activate: false });
    await tenantMemberRequest("discovered", "/member/makerspaces/4/profile");
    await publicV1Request("/public/profiles/maker.one/projects?page=1");
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get("X-Publishable-Key")).toBe("pk-discovered");
    expect(new Headers(vi.mocked(fetch).mock.calls[2][1]?.headers).get("X-Publishable-Key")).toBe("pk-current");
    expect(request).toHaveBeenCalledTimes(3);
  });
});
