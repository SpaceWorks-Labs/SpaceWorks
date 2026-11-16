import type { TelemetryAdapter } from "../controller";
import { TELEMETRY_CLIENT } from "../client";

declare global { interface Window { dataLayer?: unknown[][]; gtag?: (...args: unknown[]) => void } }
/** GA4 only emits an explicit sanitized page view; default automatic page view is disabled. */
export function ga4(measurementId: string, path: string): TelemetryAdapter {
  let script: HTMLScriptElement | undefined;
  return { purpose: "analytics", async start(signal, admitted) {
    if (signal.aborted || !admitted()) return;
    window.dataLayer = window.dataLayer ?? [];
    window.gtag = (...args: unknown[]) => window.dataLayer?.push(args);
    window.gtag("js", new Date());
    window.gtag("config", measurementId, { send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false });
    script = document.createElement("script"); script.async = true; script.referrerPolicy = "no-referrer";
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    if (signal.aborted || !admitted()) return;
    document.head.append(script);
    window.gtag("event", "page_view", { page_location: `${location.origin}${path}`, page_referrer: "", page_title: "", client: TELEMETRY_CLIENT });
  }, pageView(next) { window.gtag?.("event", "page_view", { page_location: `${location.origin}${next}`, page_referrer: "", page_title: "", client: TELEMETRY_CLIENT }); }, stop() { if (script) Reflect.set(window, `ga-disable-${measurementId}`, true); script?.remove(); } };
}

