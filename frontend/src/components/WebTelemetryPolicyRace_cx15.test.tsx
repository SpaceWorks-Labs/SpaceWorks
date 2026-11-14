import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { MixpanelSdk } from "../lib/telemetry/adapters/mixpanelSdk";

const mocks = vi.hoisted(() => ({ bootstrap: vi.fn(), digest: vi.fn() }));
vi.mock("../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "", bootstrap: null }) }));
vi.mock("../features/inventory/usePublicInventory", () => ({ useTenantBootstrap: mocks.bootstrap }));
vi.mock("../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => false }));
vi.mock("../lib/telemetry/sessionFence", () => ({ browserIdentity: () => "anonymous", subscribeBrowserIdentity: () => () => {}, resolveBrowserIdentity: vi.fn(), markAuthPresent: vi.fn() }));
// Keep consentScope real: only the browser's asynchronous SHA-256 boundary is delayed.
// Forward to a fresh real runtime per case, retaining the real controller, factory and adapter.
let runtime: typeof import("../lib/telemetry/runtime");
vi.mock("../lib/telemetry/runtime", () => ({
  updateWebTelemetry: (...args: Parameters<typeof runtime.updateWebTelemetry>) => runtime.updateWebTelemetry(...args),
  stopWebTelemetry: () => runtime.stopWebTelemetry(),
}));
import { WebTelemetry } from "./WebTelemetry";

const config = {
  pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" },
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" },
};
const selected = { token: "old-project", apiHost: "https://api.mixpanel.com", sdkHost: "https://sdk.example.test" };
const fetcher = vi.fn<typeof fetch>();
let hook: (event: { event: string }) => null;
let init: ReturnType<typeof vi.fn<MixpanelSdk["init"]>>;
let reload: ReturnType<typeof vi.fn>;
const instance = { track: vi.fn(), stop_batch_senders: vi.fn(), opt_out_tracking: vi.fn(), clear_opt_in_out_tracking: vi.fn() };
const boot = (modules = ["analytics"]) => ({ makerspace: { id: 7, slug: "lab" }, modules, telemetry: config });
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

beforeEach(async () => {
  vi.resetModules(); vi.clearAllMocks(); localStorage.clear();
  runtime = await vi.importActual("../lib/telemetry/runtime");
  history.replaceState(null, "", "/m/lab");
  // jsdom cannot replace a document; retain the production isolation call and assert it.
  reload = vi.fn();
  vi.stubGlobal("location", Object.assign(new URL(window.location.href), { reload }));
  vi.stubGlobal("crypto", { randomUUID: () => "fd875118-aee2-407a-8ef7-5ce4c6c54086", subtle: { digest: mocks.digest } });
  mocks.digest.mockResolvedValue(new Uint8Array(32).buffer);
  mocks.bootstrap.mockReturnValue({ data: boot() }); window.__MIXPANEL__ = { ...selected };
  fetcher.mockImplementation(() => new Promise(() => {})); vi.stubGlobal("fetch", fetcher);
  instance.track.mockImplementation(event => { hook({ event }); });
  init = vi.fn((_token, options) => {
    hook = (options.hooks as { before_send_events: typeof hook }).before_send_events;
    return instance;
  });
});
afterEach(() => {
  cleanup(); runtime.stopWebTelemetry();
  delete window.mixpanel; delete window.__MIXPANEL__;
  vi.unstubAllGlobals(); vi.restoreAllMocks();
});
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = () => <QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab"]}><WebTelemetry /></MemoryRouter></QueryClientProvider>;
  const view = render(tree());
  return () => view.rerender(tree());
}
async function grant() {
  fireEvent.click(await screen.findByRole("checkbox", { name: "Usage analytics" }));
  await waitFor(() => expect(document.getElementById("spaceworks-mixpanel")).not.toBeNull());
  return document.getElementById("spaceworks-mixpanel") as HTMLScriptElement;
}
async function complete(script: HTMLScriptElement) {
  window.mixpanel = { init }; script.dispatchEvent(new Event("load"));
  await act(async () => {});
}
const changes = [
  ["token", "new-project"], ["apiHost", "https://api-eu.mixpanel.com"], ["sdkHost", "https://other-sdk.example.test"],
] as const;

for (const [field, value] of changes) {
  for (const outcome of ["resolved", "rejected"] as const) {
    it(`${field} alone fences a pending SDK before the ${outcome} replacement digest`, async () => {
      const rerender = setup(), script = await grant();
      const digest = deferred<ArrayBuffer>();
      const atDigest: boolean[] = [];
      mocks.digest.mockImplementation(() => { atDigest.push(!script.isConnected); return digest.promise; });
      window.__MIXPANEL__ = { ...selected, [field]: value }; rerender();
      expect(atDigest).toEqual([true]); // Abort precedes even the call to digest.
      expect(reload).toHaveBeenCalled();
      await complete(script); // Simulate old download completion during unresolved policy.
      expect(init).toHaveBeenCalledTimes(0); expect(fetcher).toHaveBeenCalledTimes(0);
      await act(async () => {
        if (outcome === "resolved") digest.resolve(new Uint8Array(32).fill(1).buffer);
        else digest.reject(new Error("digest_unavailable"));
      });
      expect(init).toHaveBeenCalledTimes(0); expect(fetcher).toHaveBeenCalledTimes(0);
      expect(document.getElementById("spaceworks-mixpanel")).toBeNull();
      const checkbox = screen.queryByRole("checkbox", { name: "Usage analytics" });
      if (outcome === "resolved") expect(checkbox).not.toBeChecked();
      else expect(checkbox).toBeNull();
    });

    it(`${field} alone aborts active collection before the ${outcome} replacement digest`, async () => {
      const rerender = setup(), script = await grant(); await complete(script);
      expect(init).toHaveBeenCalledTimes(1); expect(init.mock.calls[0][0]).toBe(selected.token);
      expect(fetcher).toHaveBeenCalledTimes(1);
      const request = fetcher.mock.calls[0][1]!.signal!;
      expect(request.aborted).toBe(false);
      const oldHook = hook, digest = deferred<ArrayBuffer>();
      const atDigest: boolean[] = [];
      mocks.digest.mockImplementation(() => { atDigest.push(request.aborted); return digest.promise; });
      window.__MIXPANEL__ = { ...selected, [field]: value }; rerender();
      expect(atDigest).toEqual([true]);
      expect(request.aborted).toBe(true); expect(reload).toHaveBeenCalled();
      oldHook({ event: "page_view" });
      expect(fetcher).toHaveBeenCalledTimes(1); expect(init).toHaveBeenCalledTimes(1);
      await act(async () => {
        if (outcome === "resolved") digest.resolve(new Uint8Array(32).fill(1).buffer);
        else digest.reject(new Error("digest_unavailable"));
      });
      oldHook({ event: "page_view" });
      expect(fetcher).toHaveBeenCalledTimes(1); expect(init).toHaveBeenCalledTimes(1);
      expect(localStorage.getItem(`spaceworks.mixpanel.browser.v1:${selected.token}`)).toBeNull();
      expect(document.getElementById("spaceworks-mixpanel")).toBeNull();
    });
  }
}

it.each(["pending", "active"])("turning the tenant analytics module off fences %s collection and retains config", async phase => {
  const row = boot(); mocks.bootstrap.mockReturnValue({ data: row });
  const rerender = setup(), script = await grant();
  if (phase === "active") await complete(script);
  const oldHook = phase === "active" ? hook : null;
  const request = fetcher.mock.calls[0]?.[1]?.signal;
  mocks.bootstrap.mockReturnValue({ data: { ...row, modules: [] } }); rerender();
  expect(reload).toHaveBeenCalled(); expect(script.isConnected).toBe(false);
  expect(screen.queryByRole("checkbox")).toBeNull();
  if (phase === "active") { expect(request).toBeDefined(); expect(request!.aborted).toBe(true); }
  else expect(request).toBeUndefined();
  await complete(script); oldHook?.({ event: "page_view" });
  expect(init).toHaveBeenCalledTimes(phase === "active" ? 1 : 0);
  expect(fetcher).toHaveBeenCalledTimes(phase === "active" ? 1 : 0);
  expect(row.telemetry).toBe(config); expect(row.modules).toEqual(["analytics"]);
  expect(document.getElementById("spaceworks-mixpanel")).toBeNull();
});
