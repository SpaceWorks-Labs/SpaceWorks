import type { TelemetryAdapter } from "../controller";
import type { MixpanelConfig } from "../mixpanelConfig";
import { safePage } from "../policy";
import { loadMixpanel, type MixpanelInstance } from "./mixpanelSdk";

export const browserKey = (token: string) => `spaceworks.mixpanel.browser.v1:${token}`;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** No profile API, automatic capture, replay, vendor persistence or default SDK transport. */
export function mixpanel(config: MixpanelConfig, initialPath: string): TelemetryAdapter {
  let instance: MixpanelInstance | undefined;
  let active = false, browserId = "", path = initialPath;
  const requests = new Set<AbortController>();
  let allowed = () => false;
  const send = (event: { event: string }) => {
    if (!active || !allowed() || event.event !== "page_view" || safePage(new URL(location.href)) !== path) return null;
    const request = new AbortController(); requests.add(request);
    // Rebuild at the last boundary: discard ALL SDK properties, including URL, referrer,
    // device/user identifiers, attribution, names and any future default properties.
    const payload = { event: "page_view", properties: { token: config.token, distinct_id: browserId, page: path } };
    void fetch(`${config.apiHost}/track/?ip=0`, { method: "POST", mode: "cors", credentials: "omit",
      referrerPolicy: "no-referrer", redirect: "error", headers: { "Content-Type": "application/json" },
      body: JSON.stringify([payload]), signal: request.signal,
    }).catch(() => undefined).finally(() => requests.delete(request));
    return null; // Suppress the SDK transport (which otherwise attaches credentials).
  };
  return { purpose: "analytics", async start(signal, admitted) {
    if (signal.aborted || !admitted()) return;
    const sdk = await loadMixpanel(config.sdkHost, signal);
    if (!sdk || signal.aborted || !admitted()) return;
    const stored = localStorage.getItem(browserKey(config.token));
    browserId = stored && uuid.test(stored) ? stored : crypto.randomUUID();
    localStorage.setItem(browserKey(config.token), browserId);
    allowed = () => !signal.aborted && admitted(); active = true;
    instance = sdk.init(config.token, { api_host: config.apiHost, autocapture: false, track_pageview: false,
      disable_persistence: true, disable_cookie: true, batch_requests: false, batch_autostart: false,
      save_referrer: false, store_google: false, stop_utm_persistence: true, skip_first_touch_marketing: true,
      ip: false, record_sessions_percent: 0, record_heatmap_data: false, flags: false,
      track_marketing: false, remote_settings_mode: "disabled", hooks: { before_send_events: send },
    }, "spaceworks");
    if (allowed()) instance?.track("page_view");
  }, pageView(next) { path = next; if (active && allowed()) instance?.track("page_view"); }, stop() {
    active = false;
    for (const request of requests) request.abort(); requests.clear();
    try {
      instance?.stop_batch_senders();
      instance?.opt_out_tracking({ clear_persistence: true, delete_user: false });
      instance?.clear_opt_in_out_tracking({ enable_persistence: false });
    } finally {
      document.getElementById("spaceworks-mixpanel")?.remove(); delete window.mixpanel;
      try { localStorage.removeItem(browserKey(config.token)); } catch { /* collection is already stopped */ }
    }
  } };
}
