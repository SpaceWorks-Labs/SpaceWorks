import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";
import type { AdapterFactory } from "./controller";
import type { Consent } from "./policy";
import { replayRoute } from "./replayRoutes";

/** Defence in depth behind the server allowlist: a bare https origin, or nothing. */
export function safeOrigin(value: string): string | undefined {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash || /[\s\\]/.test(value)) return undefined;
    return url.origin;
  } catch { return undefined; }
}

/** Import providers only after the controller has admitted the corresponding purpose. */
export function providerFactories(config: WebTelemetryConfig, consent: Consent, path: string): AdapterFactory[] {
  const result: AdapterFactory[] = [];
  const p = config.pageview, r = config.replay, f = config.firebase;
  const firebase = { apiKey: f.api_key, authDomain: f.auth_domain, projectId: f.project_id, appId: f.app_id, measurementId: f.measurement_id };
  const pageOrigin = p.endpoint ? safeOrigin(p.endpoint) : undefined, replayOrigin = r.endpoint ? safeOrigin(r.endpoint) : undefined;
  const pageOriginOk = !p.endpoint || Boolean(pageOrigin), replayOriginOk = !r.endpoint || Boolean(replayOrigin);
  if (p.provider === "plausible" && pageOriginOk) result.push({ purpose: "analytics", load: async () => (await import("./adapters/plausible")).plausible(p.site_id, pageOrigin || "https://plausible.io", path) });
  if (p.provider === "umami" && pageOrigin) result.push({ purpose: "analytics", load: async () => (await import("./adapters/umami")).umami(p.site_id, pageOrigin, path) });
  if (p.provider === "ga4") result.push({ purpose: "analytics", load: async () => (await import("./adapters/ga4")).ga4(p.site_id, path) });
  if (p.provider === "firebase") result.push({ purpose: "analytics", load: async () => (await import("./adapters/firebaseAnalytics")).firebaseAnalytics(firebase, path) });
  const phHost = "https://us.i.posthog.com";
  const phAnalytics = p.provider === "posthog" && consent.analytics && pageOriginOk;
  const replayAllowed = replayRoute(r.provider, path);
  // One shared SDK instance: replay rides along only when it targets the very same project and origin,
  // never silently into the analytics project (the server rejects the mismatch; this guards stale rows).
  const sameProject = p.site_id === r.site_id && (pageOrigin || phHost) === (replayOrigin || phHost);
  const phReplay = r.provider === "posthog" && consent.replay && replayAllowed && replayOriginOk && (!phAnalytics || sameProject);
  if (phAnalytics || phReplay) result.push({ purpose: phAnalytics ? "analytics" : "replay", load: async () => {
    const [siteId, origin] = phAnalytics ? [p.site_id, pageOrigin] : [r.site_id, replayOrigin];
    return (await import("./adapters/posthog")).posthog(siteId, origin || phHost, phAnalytics, phReplay, path);
  } });
  if (r.provider === "clarity" && replayAllowed) result.push({ purpose: "replay", load: async () => (await import("./adapters/clarity")).clarity(r.site_id) });
  if (config.diagnostics.sentry.enabled) result.push({ purpose: "diagnostics", load: async () => (await import("./adapters/sentry")).sentry(config.diagnostics.sentry.dsn, config.diagnostics.sentry.sample_rate) });
  if (config.diagnostics.firebase_performance.enabled) result.push({ purpose: "diagnostics", load: async () => (await import("./adapters/firebasePerformance")).firebasePerformance(firebase, config.diagnostics.firebase_performance.sample_rate) });
  return result;
}



