import type { TelemetryAdapter } from "../controller";

type FirebaseConfig = { apiKey: string; authDomain: string; projectId: string; appId: string; measurementId: string };
export function firebaseAnalytics(config: FirebaseConfig, path: string): TelemetryAdapter {
  let firebaseSdk: typeof import("firebase/analytics") | undefined;
  let analytics: import("firebase/analytics").Analytics | undefined;
  return { purpose: "analytics", async start(signal, admitted) {
    const [app, sdk] = await Promise.all([import("firebase/app"), import("firebase/analytics")]);
    if (signal.aborted || !admitted() || !(await sdk.isSupported())) return;
    if (signal.aborted || !admitted()) return;
    const firebase = app.getApps().find(item => item.name === "spaceworks-telemetry") ?? app.initializeApp(config, "spaceworks-telemetry");
    firebaseSdk = sdk;
    analytics = sdk.initializeAnalytics(firebase, { config: { send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false } });
    sdk.logEvent(analytics, "page_view", { page_location: `${location.origin}${path}`, page_referrer: "", page_title: "" });
  }, pageView(next) { if (analytics) firebaseSdk?.logEvent(analytics, "page_view", { page_location: `${location.origin}${next}`, page_referrer: "", page_title: "" }); }, stop() { if (analytics) firebaseSdk?.setAnalyticsCollectionEnabled(analytics, false); } };
}


