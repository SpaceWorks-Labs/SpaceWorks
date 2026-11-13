import { afterEach, expect, it, vi } from "vitest";
import { beforeSessionTransition, browserIdentity, resolveBrowserIdentity } from "./sessionFence";
afterEach(() => vi.unstubAllGlobals());
it("does not admit a network failure as an anonymous browser", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  expect(await resolveBrowserIdentity("/api/v1/auth/browser-state")).toBe("unknown");
});
it("does not let a stale anonymous response override a newly authenticated transition", async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const pending = resolveBrowserIdentity("/api/v1/auth/browser-state");
  beforeSessionTransition(); resolve(new Response(JSON.stringify({ state: "anonymous" }), { status: 200 }));
  await pending; expect(browserIdentity()).toBe("auth_present");
});
it("does not treat a refresh-cookie authenticated public session as anonymous", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ state: "auth_present" }), { status: 200 })));
  expect(await resolveBrowserIdentity("/api/v1/auth/browser-state")).toBe("auth_present");
});
