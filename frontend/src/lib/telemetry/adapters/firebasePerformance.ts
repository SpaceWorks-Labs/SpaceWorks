import type { TelemetryAdapter } from "../controller";
import { TELEMETRY_CLIENT } from "../client";

/** Firebase automatic instrumentation remains off; only explicit sanitized traces may be added. */
export function firebasePerformance(config: { apiKey: string; authDomain: string; projectId: string; appId: string }, rate: number): TelemetryAdapter {
  let perf: import("firebase/performance").FirebasePerformance | undefined;
  return { purpose: "diagnostics", async start(signal, admitted) {
    if (Math.random() >= rate) return;
    const [app, performance] = await Promise.all([import("firebase/app"), import("firebase/performance")]);
    if (signal.aborted || !admitted()) return;
    const firebase = app.getApps().find(item => item.name === "spaceworks-telemetry") ?? app.initializeApp(config, "spaceworks-telemetry");
    perf = performance.initializePerformance(firebase, { instrumentationEnabled: false, dataCollectionEnabled: true });
    if (signal.aborted || !admitted()) return;
    const trace = performance.trace(perf, "public_document_ready");
    const navigation = window.performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    trace.putAttribute("client", TELEMETRY_CLIENT);
    trace.start();
    if (navigation && Number.isFinite(navigation.domContentLoadedEventEnd)) trace.putMetric("dom_ready_ms", Math.min(120000, Math.max(0, Math.round(navigation.domContentLoadedEventEnd))));
    trace.stop();
  }, stop() { if (perf) { perf.instrumentationEnabled = false; perf.dataCollectionEnabled = false; } } };
}

