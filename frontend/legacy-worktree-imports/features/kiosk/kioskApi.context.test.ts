// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: written for string session contexts ("member", "staff:<slug>"); release SessionContext is "person" | "platform".
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "../../lib/api";
import { contextForRoute, setRouteSessionContext } from "../../lib/api/sessionContext";
import { loadWorkPackage, prepareEvidence, runOnlineCommand, takeOperatorLease } from "./kioskApi";

const contexts = ["member", "platform", "staff:forge", "staff:other"] as const;
const json = (body: object, status = 200) => new Response(JSON.stringify(body), { status });
beforeEach(() => {
  setRouteSessionContext(contextForRoute("/m/forge/kiosk/token"));
  contexts.forEach(context => setAccessToken(`token-${context}`, context));
});
afterEach(() => {
  contexts.forEach(context => clearAccessToken(context));
  setRouteSessionContext("member"); vi.unstubAllGlobals();
});

it("all operator requests carry only the tenant staff token plus the Station cookie", async () => {
  const fetcher = vi.fn(async (_url: string, options: RequestInit) => {
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer token-staff:forge");
    expect(options.credentials).toBe("include");
    expect(options.cache).toBe("no-store");
    expect(new Headers(options.headers).get("X-Station-CSRF")).toBe("1");
    return json({});
  });
  vi.stubGlobal("fetch", fetcher);
  await takeOperatorLease("token");
  await loadWorkPackage("token", "lease", "reviewed_request", 7);
  await prepareEvidence("token", "lease", { evidence_type: "issue" });
  await runOnlineCommand("token", "lease", "resolve_qr", { payload: "qr" });
  expect(fetcher).toHaveBeenCalledTimes(4);
});

it("refreshes only the initiating tenant staff cookie after an expired token", async () => {
  let calls = 0;
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      expect(JSON.parse(options.body as string)).toEqual({ context: "staff:forge" });
      return json({ access: "renewed-staff" });
    }
    calls += 1;
    if (calls === 1) return json({ code: "token_not_valid" }, 401);
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer renewed-staff");
    return json({});
  });
  vi.stubGlobal("fetch", fetcher);
  await takeOperatorLease("token");
  expect(calls).toBe(2);
});

it.each(["member", "platform"] as const)("refuses operator calls in the %s context before sending credentials", async context => {
  setRouteSessionContext(context);
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  await expect(takeOperatorLease("token")).rejects.toThrow("tenant staff context");
  expect(fetcher).not.toHaveBeenCalled();
});
