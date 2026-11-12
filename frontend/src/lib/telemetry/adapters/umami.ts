import type { TelemetryAdapter } from "../controller";
import { TELEMETRY_CLIENT } from "../client";

declare global { interface Window { umami?: { track: (payload: { url: string; title: string; referrer: string; data?: { client: string } }) => void } } }
/** Official Umami tracker, manually invoked after consent; no automatic pageviews. */
export function umami(siteId: string, origin: string, path: string): TelemetryAdapter {
  let script: HTMLScriptElement | undefined;
  return { purpose: "analytics", async start(signal, admitted) {
    if (signal.aborted || !admitted()) return;
    script = document.createElement("script"); script.src = `${origin}/script.js`; script.defer = true;
    script.dataset.websiteId = siteId; script.dataset.autoTrack = "false"; script.referrerPolicy = "no-referrer";
    await new Promise<void>((resolve, reject) => {
      script!.onload = () => resolve(); script!.onerror = () => reject(new Error("Tracker unavailable")); // i18n-ignore: tracker load failure; TelemetryController catches it and stops the adapter, never rendered.
      signal.addEventListener("abort", () => { script?.remove(); reject(new Error("Cancelled")); }, { once: true }); // i18n-ignore: abort signal; TelemetryController catches it, never rendered.
      if (admitted() && !signal.aborted) document.head.append(script!); else reject(new Error("Cancelled")); // i18n-ignore: abort signal; TelemetryController catches it, never rendered.
    });
    if (!signal.aborted && admitted()) window.umami?.track({ url: path, title: "", referrer: "", data: { client: TELEMETRY_CLIENT } });
  }, pageView(next) { window.umami?.track({ url: next, title: "", referrer: "", data: { client: TELEMETRY_CLIENT } }); }, stop() { script?.remove(); } };
}

