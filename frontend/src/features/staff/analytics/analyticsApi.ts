import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";

/** Lane L25 (#163B): one space's Metabase, or the platform-wide one (superadmin). */
export type AnalyticsScope = { kind: "space"; makerspaceId: number } | { kind: "platform" };

export type AnalyticsDashboard = { id: number; title: string };

export type AnalyticsSummary = {
  available: boolean;
  reason: string;
  views_version: number;
  configured: boolean;
  dashboards: AnalyticsDashboard[];
  can_manage: boolean;
};

export type AnalyticsConnection = Omit<AnalyticsSummary, "can_manage"> & {
  metabase_url: string;
  embed_secret_set: boolean;
  show_member_details: boolean | null;
  login: { role: string; exists: boolean; created_at: string | null; rotated_at: string | null };
  database: { host: string; port: number; database: string; schema: string };
};

export type AnalyticsConnectionPatch = Partial<{
  metabase_url: string;
  embed_secret: string;
  dashboards: AnalyticsDashboard[];
  show_member_details: boolean;
}>;

/** Returned once, by create and rotate; never stored in the query cache. */
export type AnalyticsCredentials = {
  role: string; password: string; host: string; port: number; database: string; schema: string;
};

export type AnalyticsEmbed = { url: string; expires_at: string };

export function analyticsBase(scope: AnalyticsScope) {
  return scope.kind === "platform" ? "/admin/platform/analytics" : `/admin/makerspaces/${scope.makerspaceId}/analytics`;
}

const scopeKey = (scope: AnalyticsScope) => (scope.kind === "platform" ? "platform" : scope.makerspaceId);

export const analyticsKeys = {
  all: (scope: AnalyticsScope) => ["analytics", scopeKey(scope)] as const,
  summary: (scope: AnalyticsScope) => ["analytics", scopeKey(scope), "summary"] as const,
  connection: (scope: AnalyticsScope) => ["analytics", scopeKey(scope), "connection"] as const,
};

export function useAnalyticsSummary(scope: AnalyticsScope) {
  return useQuery({
    queryKey: analyticsKeys.summary(scope),
    queryFn: () => staffRequest<AnalyticsSummary>(analyticsBase(scope)),
  });
}

export function useAnalyticsConnection(scope: AnalyticsScope, enabled: boolean) {
  return useQuery({
    queryKey: analyticsKeys.connection(scope),
    queryFn: () => staffRequest<AnalyticsConnection>(`${analyticsBase(scope)}/connection`),
    enabled,
  });
}

/** Signed embed URLs expire after ten minutes: never cached, refetched on demand. */
export function useAnalyticsEmbed(scope: AnalyticsScope, dashboardId: number | null) {
  return useQuery({
    queryKey: [...analyticsKeys.all(scope), "embed", dashboardId] as const,
    queryFn: () => staffRequest<AnalyticsEmbed>(`${analyticsBase(scope)}/dashboards/${dashboardId}/embed`),
    enabled: dashboardId !== null,
    gcTime: 0,
    staleTime: 8 * 60 * 1000,
    refetchInterval: 8 * 60 * 1000,
  });
}

function useInvalidate(scope: AnalyticsScope) {
  const queryClient = useQueryClient();
  return () => Promise.all([
    queryClient.invalidateQueries({ queryKey: analyticsKeys.all(scope) }),
    queryClient.invalidateQueries({ queryKey: ["audit"] }),
  ]);
}

export function useUpdateAnalyticsConnection(scope: AnalyticsScope) {
  const invalidate = useInvalidate(scope);
  return useMutation({
    mutationFn: (changes: AnalyticsConnectionPatch) => staffRequest<AnalyticsConnection>(
      `${analyticsBase(scope)}/connection`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: invalidate,
  });
}

export function useAnalyticsLogin(scope: AnalyticsScope) {
  const invalidate = useInvalidate(scope);
  const base = analyticsBase(scope);
  const create = useMutation({
    mutationFn: () => staffRequest<AnalyticsCredentials>(`${base}/login`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const rotate = useMutation({
    mutationFn: () => staffRequest<AnalyticsCredentials>(`${base}/login/rotate`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const revoke = useMutation({
    mutationFn: () => staffRequest<void>(`${base}/login`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  return { create, rotate, revoke };
}
