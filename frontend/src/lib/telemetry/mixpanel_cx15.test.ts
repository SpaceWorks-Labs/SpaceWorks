import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TelemetryController } from "./controller";
import { deniedConsent, safePage } from "./policy";
import { providerFactories } from "./providers";
import { deploymentMixpanel, type MixpanelConfig } from "./mixpanelConfig";
import { browserKey } from "./adapters/mixpanel";
import type { MixpanelSdk } from "./adapters/mixpanelSdk";
import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";

const config: WebTelemetryConfig = {
  pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" },
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" },
};
const selected: MixpanelConfig = { token: "cx15-public-token", apiHost: "https://api-eu.mixpanel.com", sdkHost: "https://sdk.example.test" };
const consent = { ...deniedConsent(), analytics: true };
let controller: TelemetryController;
const fetcher = vi.fn<typeof fetch>();
let hook: (event: { event: string; properties: Record<string, unknown> }) => null;
let options: Record<string, unknown>;
let init: ReturnType<typeof vi.fn<MixpanelSdk["init"]>>;
const instance = { track: vi.fn(), stop_batch_senders: vi.fn(), opt_out_tracking: vi.fn(), clear_opt_in_out_tracking: vi.fn() };

beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear();
  history.replaceState(null, "", "/m/PrivateWorkshop/items/774");
  fetcher.mockResolvedValue(new Response("1")); vi.stubGlobal("fetch", fetcher);
  controller = new TelemetryController();
  instance.track.mockImplementation(event => {
    expect(hook({ event, properties: { name: "Private Name", email: "private@example.test", handle: "secret-handle",
      user_id: 19, makerspace: "PrivateWorkshop", text: "private remarks", $current_url: location.href, $referrer: document.referrer,
      distinct_id: "account-19", page: location.pathname, token: "untrusted" } })).toBeNull();
  });
  init = vi.fn((_token, settings) => {
    options = settings; hook = (settings.hooks as { before_send_events: typeof hook }).before_send_events;
    return instance;
  });
});
afterEach(() => {
  controller.stop(); document.getElementById("spaceworks-mixpanel")?.remove();
  delete window.mixpanel; delete window.__MIXPANEL__; vi.unstubAllGlobals(); vi.restoreAllMocks();
});
function factories(policy = config) { return providerFactories(policy, consent, safePage(new URL(location.href))!, selected); }
async function loaded() {
  await vi.waitFor(() => expect(document.getElementById("spaceworks-mixpanel")).not.toBeNull());
  const script = document.getElementById("spaceworks-mixpanel") as HTMLScriptElement;
  expect(script.src).toBe(`${selected.sdkHost}/libs/mixpanel-2-latest.min.js`);
  expect(script.referrerPolicy).toBe("no-referrer");
  window.mixpanel = { init }; script.dispatchEvent(new Event("load"));
}
async function start() {
  const pending = controller.start(new URL(location.href), consent, factories(), () => true);
  await loaded(); await pending;
}

it("disabled means no script, request, SDK initialization or storage", async () => {
  expect(deploymentMixpanel()).toBeNull();
  await controller.start(new URL(location.href), consent, providerFactories(config, consent, "/m/:slug/items/:itemId"), () => true);
  expect(init).not.toHaveBeenCalled(); expect(fetcher).not.toHaveBeenCalled();
  expect(document.querySelector("script")).toBeNull(); expect(localStorage.length).toBe(0);
});

it("enabled without analytics consent never invokes even the adapter loader", async () => {
  const selectedFactories = factories(), load = vi.spyOn(selectedFactories[0], "load");
  await controller.start(new URL(location.href), { ...deniedConsent(), replay: true, diagnostics: true }, selectedFactories, () => true);
  expect(load).not.toHaveBeenCalled(); expect(document.querySelector("script")).toBeNull();
  expect(init).not.toHaveBeenCalled(); expect(fetcher).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0);
});

it("after consent sends exactly the allowlisted event and properties, discarding all SDK PII", async () => {
  await start();
  expect(init).toHaveBeenCalledWith(selected.token, expect.any(Object), "spaceworks");
  expect(options).toMatchObject({ api_host: selected.apiHost, autocapture: false, track_pageview: false, disable_persistence: true,
    disable_cookie: true, batch_requests: false, record_sessions_percent: 0, flags: false, ip: false,
    save_referrer: false, stop_utm_persistence: true, track_marketing: false, remote_settings_mode: "disabled" });
  expect(fetcher).toHaveBeenCalledTimes(1);
  const [target, request] = fetcher.mock.calls[0];
  expect(target).toBe("https://api-eu.mixpanel.com/track/?ip=0");
  expect(request).toMatchObject({ credentials: "omit", referrerPolicy: "no-referrer", redirect: "error", method: "POST", mode: "cors", headers: { "Content-Type": "application/json" } });
  const id = localStorage.getItem(browserKey(selected.token));
  expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  const payload = JSON.parse(request!.body as string);
  expect(payload).toEqual([{ event: "page_view", properties: { token: selected.token, distinct_id: id, page: "/m/:slug/items/:itemId" } }]);
  expect(Object.keys(payload[0]).sort()).toEqual(["event", "properties"]);
  expect(Object.keys(payload[0].properties).sort()).toEqual(["distinct_id", "page", "token"]);
  expect(sessionStorage.length).toBe(0); expect(document.cookie).toBe("");
  hook({ event: "unknown_event", properties: {} }); expect(fetcher).toHaveBeenCalledTimes(1);
});

it("withdrawal aborts transport, clears storage and SDK, and blocks queued events", async () => {
  fetcher.mockImplementation(() => new Promise(() => {}));
  await start(); const signal = fetcher.mock.calls[0][1]!.signal!;
  controller.stop(); controller.pageView("/about"); hook({ event: "page_view", properties: {} });
  expect(signal.aborted).toBe(true); expect(localStorage.getItem(browserKey(selected.token))).toBeNull();
  expect(window.mixpanel).toBeUndefined(); expect(document.getElementById("spaceworks-mixpanel")).toBeNull();
  expect(instance.opt_out_tracking).toHaveBeenCalledWith({ clear_persistence: true, delete_user: false });
  expect(instance.clear_opt_in_out_tracking).toHaveBeenCalledWith({ enable_persistence: false });
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("withdrawal while the SDK is loading prevents initialization and resolves the pending start", async () => {
  const pending = controller.start(new URL(location.href), consent, factories(), () => true);
  await vi.waitFor(() => expect(document.getElementById("spaceworks-mixpanel")).not.toBeNull());
  const script = document.getElementById("spaceworks-mixpanel")!;
  controller.stop(); script.dispatchEvent(new Event("load")); await pending;
  expect(init).not.toHaveBeenCalled(); expect(fetcher).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0);
  expect(window.mixpanel).toBeUndefined(); expect(script.isConnected).toBe(false);
});

it.each(["/admin", "/m/PrivateWorkshop/member", "/unknown", "/about?email=secret@example.test", "/about#private", "/claim/token"])("fails closed for %s", async path => {
  history.replaceState(null, "", path);
  await controller.start(new URL(location.href), consent, factories(), () => true);
  expect(document.getElementById("spaceworks-mixpanel")).toBeNull(); expect(init).not.toHaveBeenCalled(); expect(fetcher).not.toHaveBeenCalled();
});

it("uses the same random browser ID on safe navigation but never accepts a raw path", async () => {
  await start(); const id = localStorage.getItem(browserKey(selected.token));
  history.replaceState(null, "", "/about"); controller.pageView("/about");
  expect(JSON.parse(fetcher.mock.calls[1][1]!.body as string)).toEqual([{ event: "page_view", properties: { token: selected.token, distinct_id: id, page: "/about" } }]);
  controller.pageView("/m/PrivateWorkshop/items/774"); expect(fetcher).toHaveBeenCalledTimes(2);
});

it("selects only one page provider even with a tenant GA4 configuration", () => {
  expect(factories({ ...config, pageview: { provider: "ga4", site_id: "G-PRIVATE", endpoint: "" } }).map(row => row.purpose)).toEqual(["analytics"]);
});

it.each(["http://example.test", "https://*.example.test", "https://example.test/path", "https://user@example.test", "https://example.test\n"])("refuses unsafe runtime hosts %s", host => {
  window.__MIXPANEL__ = { ...selected, apiHost: host }; expect(deploymentMixpanel()).toBeNull();
  window.__MIXPANEL__ = { ...selected, sdkHost: host }; expect(deploymentMixpanel()).toBeNull();
});

it("SDK download failure leaves analytics inert", async () => {
  const pending = controller.start(new URL(location.href), consent, factories(), () => true);
  await vi.waitFor(() => expect(document.getElementById("spaceworks-mixpanel")).not.toBeNull());
  document.getElementById("spaceworks-mixpanel")!.dispatchEvent(new Event("error")); await pending;
  expect(init).not.toHaveBeenCalled(); expect(fetcher).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0);
});

it("SDK initialization failure clears the browser identifier and never sends a payload", async () => {
  init.mockImplementation(() => { throw new Error("sdk_failure"); });
  await start();
  expect(fetcher).not.toHaveBeenCalled(); expect(localStorage.getItem(browserKey(selected.token))).toBeNull();
  expect(document.getElementById("spaceworks-mixpanel")).toBeNull(); expect(window.mixpanel).toBeUndefined();
});

it("storage failure fails closed before initialization or collection", async () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage_unavailable"); });
  await start();
  expect(init).not.toHaveBeenCalled(); expect(fetcher).not.toHaveBeenCalled();
  expect(document.getElementById("spaceworks-mixpanel")).toBeNull(); expect(window.mixpanel).toBeUndefined();
});

it("collector failure is contained and never retries or persists an event", async () => {
  fetcher.mockRejectedValue(new Error("collector_unavailable"));
  await start(); await Promise.resolve();
  expect(fetcher).toHaveBeenCalledTimes(1); expect(sessionStorage.length).toBe(0);
  expect(Object.keys(localStorage)).toEqual([browserKey(selected.token)]);
});
