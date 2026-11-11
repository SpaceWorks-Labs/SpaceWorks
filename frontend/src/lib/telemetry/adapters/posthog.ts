import type { TelemetryAdapter } from "../controller";

/** The caller consolidates same-project PostHog analytics and replay into one instance. */
export function posthog(projectId: string, origin: string, analytics: boolean, replay: boolean, path: string): TelemetryAdapter {
  let currentPath = path;
  let instance: typeof import("posthog-js/dist/module.slim").default | undefined;
  return { purpose: analytics ? "analytics" : "replay", async start(signal, admitted) {
    const [{ default: sdk }, extensions] = await Promise.all([
      import("posthog-js/dist/module.slim"), import("posthog-js/dist/extension-bundles"),
    ]);
    if (signal.aborted || !admitted()) return;
    instance = sdk;
    sdk.init(projectId, { api_host: origin, autocapture: false, capture_pageview: false, capture_pageleave: false,
      opt_out_capturing_by_default: true, disable_session_recording: true, disable_surveys: true,
      advanced_disable_feature_flags: true, advanced_disable_feature_flags_on_first_load: true,
      enable_recording_console_log: false, capture_performance: false,
      before_send: event => {
        if (event.event === "$snapshot" && replay) return event;
        if (event.event !== "$pageview" || !analytics) return null;
        return { ...event, properties: { token: projectId, distinct_id: event.properties.distinct_id, $session_id: event.properties.$session_id, $current_url: `${location.origin}${currentPath}` }, $set: undefined, $set_once: undefined, $unset: undefined };
      },
      __extensionClasses: replay ? { ...extensions.SessionReplayExtensions } : {},
      session_recording: { maskAllInputs: true, maskAllElementAttributes: true, recordHeaders: false, recordBody: false, maskTextSelector: "*", blockSelector: "img,video,canvas,iframe,[data-replay-block]", maskCapturedNetworkRequestFn: () => null } });
    if (signal.aborted || !admitted()) { sdk.opt_out_capturing(); return; }
    sdk.opt_in_capturing({ captureEventName: false });
    if (replay) sdk.startSessionRecording();
    if (analytics) sdk.capture("$pageview", { $current_url: `${location.origin}${path}` });
  }, pageView(next) { currentPath = next; if (analytics) instance?.capture("$pageview", { $current_url: `${location.origin}${next}` }); }, stop() { instance?.stopSessionRecording(); instance?.opt_out_capturing(); } };
}






