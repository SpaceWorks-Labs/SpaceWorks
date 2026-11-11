import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { AnalyticsScope } from "./analyticsApi";

export type WebTelemetryConfig = {
  pageview: { provider: "none" | "plausible" | "umami" | "ga4" | "firebase" | "posthog"; site_id: string; endpoint: string };
  replay: { provider: "none" | "clarity" | "posthog"; site_id: string; endpoint: string };
  diagnostics: { sentry: { enabled: boolean; dsn: string; sample_rate: number }; firebase_performance: { enabled: boolean; sample_rate: number } };
  firebase: { api_key: string; auth_domain: string; project_id: string; app_id: string; messaging_sender_id: string; measurement_id: string; vapid_public_key: string };
};
const base = (scope: AnalyticsScope) => scope.kind === "platform" ? "/admin/platform/telemetry" : `/admin/makerspaces/${scope.makerspaceId}/telemetry`;
const key = (scope: AnalyticsScope) => ["web-telemetry", scope.kind === "platform" ? "platform" : scope.makerspaceId] as const;
export function useWebTelemetry(scope: AnalyticsScope) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: key(scope), queryFn: () => staffRequest<{ config: WebTelemetryConfig }>(base(scope)), retry: false });
  const save = useMutation({ mutationFn: (config: WebTelemetryConfig) => staffRequest<{ config: WebTelemetryConfig }>(base(scope), { method: "PATCH", body: JSON.stringify({ config }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: key(scope) }); void client.invalidateQueries({ queryKey: ["audit"] }); } });
  return { query, save };
}
