import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";

/** Backend controls this flag; explicit configuration and module-off deny fallback. */
export function legacySelected(config: WebTelemetryConfig | undefined, allowed: boolean, legacyConfigured: boolean): boolean {
  return Boolean(config && allowed && legacyConfigured && config.pageview.provider === "none");
}
