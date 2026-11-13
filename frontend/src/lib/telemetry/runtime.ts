import * as sdk from "../webAnalytics"; // already in the entry chunk (main.tsx), so a dynamic import would not split it
import { browserIdentity } from "./sessionFence";
import { TelemetryController } from "./controller";
import { installTelemetryBoundary } from "./boundary";
import { safePage, type Consent } from "./policy";
import { replayRoute } from "./replayRoutes";
import { providerFactories } from "./providers";
import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";

const controller = new TelemetryController();
let everLoaded = false, generation = 0, currentBinding: string | null = null, currentNavigation: string | null = null, ready = false;
let replayPolicyProvider = "none";
let pendingStart: Promise<void> | null = null, queued: { navigation: string; path: string } | null = null;
/** Install once before React; provider execution latches isolation until document replacement. */
export function installWebTelemetryBoundary() {
  return installTelemetryBoundary(() => everLoaded, () => { generation++; controller.stop(); }, url => url.pathname.match(/^\/m\/([^/]+)/)?.[1] ?? "root", (previous, next) => replayRoute(replayPolicyProvider, safePage(previous)) !== replayRoute(replayPolicyProvider, safePage(next)));
}
export async function updateWebTelemetry(binding: string, config: WebTelemetryConfig, consent: Consent, url: URL, verifiedAnonymous: boolean, legacy = false) {
  if (!verifiedAnonymous || browserIdentity() !== "anonymous") { stopWebTelemetry(); return; }
  const path = safePage(url);
  replayPolicyProvider = consent.replay ? config.replay.provider : "none";
  if (path && currentBinding === binding && pendingStart) { queued = { navigation: url.href, path }; await pendingStart; return; }
  if (path && currentBinding === binding && ready && (everLoaded || !replayRoute(replayPolicyProvider, path))) { if (currentNavigation !== url.href) { currentNavigation = url.href; controller.pageView(path); } return; }
  const myGeneration = ++generation; ready = false;
  if (everLoaded && currentBinding !== null && binding !== currentBinding) { controller.stop(); location.reload(); return; }
  currentBinding = binding;
  if (!path) { controller.stop(); return; }
  currentNavigation = url.href; queued = null;
  const configured = legacy ? [{ purpose: "analytics" as const, load: async () => {
    return { purpose: "analytics" as const, async start(signal: AbortSignal, admitted: () => boolean) { if (!signal.aborted && admitted()) sdk.pageView(url); }, pageView() { sdk.pageView(new URL(window.location.href)); }, stop() { sdk.removeAnalytics(); } };
  } }] : providerFactories(config, consent, path);
  const factories = configured.map(factory => ({ ...factory, load: async () => {
    everLoaded = true; return factory.load();
  } }));
  const start = controller.start(url, consent, factories, () => generation === myGeneration && currentBinding === binding && browserIdentity() === "anonymous");
  pendingStart = start; await start;
  if (pendingStart === start) pendingStart = null;
  if (generation === myGeneration) {
    ready = true;
    const next = queued as { navigation: string; path: string } | null;
    if (next && next.navigation !== currentNavigation) { currentNavigation = next.navigation; controller.pageView(next.path); }
    queued = null;
  }
}
export function fenceWebTelemetry(): boolean {
  generation++; ready = false; pendingStart = null; queued = null; controller.stop();
  if (everLoaded) { location.reload(); return true; }
  return false;
}
export function stopWebTelemetry() { generation++; ready = false; pendingStart = null; queued = null; controller.stop(); if (everLoaded) location.reload(); }












