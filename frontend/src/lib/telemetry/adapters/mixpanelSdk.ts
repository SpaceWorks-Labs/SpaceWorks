/** Only the tiny API surface this adapter needs; the vendor script is never statically imported. */
export type MixpanelInstance = {
  track: (event: string) => void;
  stop_batch_senders: () => void;
  opt_out_tracking: (options: { clear_persistence: boolean; delete_user: boolean }) => void;
  clear_opt_in_out_tracking: (options: { enable_persistence: boolean }) => void;
};
export type MixpanelSdk = { init: (token: string, config: Record<string, unknown>, name: string) => MixpanelInstance };
declare global { interface Window { mixpanel?: MixpanelSdk | { __SV: number; _i: never[] } } }

/** The empty snippet queue cannot initialize a project or emit an event while the SDK downloads. */
export function loadMixpanel(host: string, signal: AbortSignal): Promise<MixpanelSdk | null> {
  return new Promise((resolve, reject) => {
    // Anonymous CORS still includes same-origin credentials: mirrors must be external.
    if (signal.aborted || new URL(host).origin === window.location.origin) { resolve(null); return; }
    const script = document.createElement("script");
    script.id = "spaceworks-mixpanel";
    script.crossOrigin = "anonymous";
    script.referrerPolicy = "no-referrer";
    script.async = true;
    script.src = `${host}/libs/mixpanel-2-latest.min.js`;
    window.mixpanel = { __SV: 1.2, _i: [] };
    const cleanup = () => { signal.removeEventListener("abort", abort); script.onload = null; script.onerror = null; };
    const abort = () => { cleanup(); script.remove(); delete window.mixpanel; resolve(null); };
    signal.addEventListener("abort", abort, { once: true });
    script.onload = () => {
      cleanup();
      const sdk = window.mixpanel;
      if (sdk && "init" in sdk && typeof sdk.init === "function") resolve(sdk);
      else { script.remove(); delete window.mixpanel; reject(new Error("mixpanel_sdk_unavailable")); }
    };
    script.onerror = () => { cleanup(); script.remove(); delete window.mixpanel; reject(new Error("mixpanel_sdk_unavailable")); };
    document.head.append(script);
  });
}
