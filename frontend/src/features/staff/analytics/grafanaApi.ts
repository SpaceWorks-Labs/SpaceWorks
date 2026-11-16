import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { type AnalyticsProvider, type AnalyticsScope, analyticsKeys } from "./analyticsApi";

/** Decision 263: Grafana beside Metabase, per space and for the platform (superadmin). */
export type GrafanaMode = "public" | "render";
export type GrafanaDashboard = { uid: string; title: string; mode: GrafanaMode };
export type GrafanaDashboardEntry = GrafanaDashboard & { public_token: string };

export type GrafanaSummary = {
  provider: AnalyticsProvider;
  configured: boolean;
  dashboards: GrafanaDashboard[];
  can_manage: boolean;
  views_version: number;
};

export type GrafanaConnection = {
  provider: AnalyticsProvider;
  grafana_url: string;
  token_set: boolean;
  token_updated_at: string | null;
  org_id: number;
  dashboards: GrafanaDashboardEntry[];
  login_role: string;
  database: { host: string; port: number; database: string; schema: string };
  private_hosts_allowed: boolean;
};

export type GrafanaConnectionPatch = Partial<{
  provider: AnalyticsProvider;
  grafana_url: string;
  org_id: number;
  dashboards: GrafanaDashboardEntry[];
}>;

export type GrafanaTestResult = {
  ok: boolean;
  version: string;
  dashboards_found: number | null;
  checks: { name: "health" | "search"; ok: boolean; detail: string }[];
};

export type GrafanaEmbed = { mode: "public"; url: string };

export type GrafanaBundle = {
  format: string;
  version: number;
  scope: string;
  makerspace_id: number | null;
  views_version: number;
  areas: string[];
  datasource: { datasources?: { secureJsonData?: { password?: string } }[] } & Record<string, unknown>;
  dashboards: { area: string; title: string; uid: string; dashboard: unknown }[];
  instructions: string[];
};

export function grafanaBase(scope: AnalyticsScope) {
  return scope.kind === "platform" ? "/admin/platform/grafana" : `/admin/makerspaces/${scope.makerspaceId}/grafana`;
}

export const grafanaKeys = {
  all: (scope: AnalyticsScope) => [...analyticsKeys.all(scope), "grafana"] as const,
  summary: (scope: AnalyticsScope) => [...analyticsKeys.all(scope), "grafana", "summary"] as const,
  connection: (scope: AnalyticsScope) => [...analyticsKeys.all(scope), "grafana", "connection"] as const,
};

export function useGrafanaSummary(scope: AnalyticsScope, enabled: boolean) {
  return useQuery({
    queryKey: grafanaKeys.summary(scope),
    queryFn: () => staffRequest<GrafanaSummary>(grafanaBase(scope)),
    enabled,
  });
}

export function useGrafanaConnection(scope: AnalyticsScope) {
  return useQuery({
    queryKey: grafanaKeys.connection(scope),
    queryFn: () => staffRequest<GrafanaConnection>(`${grafanaBase(scope)}/connection`),
  });
}

/** Public dashboard links do not expire; still never cached across mounts. */
export function useGrafanaEmbed(scope: AnalyticsScope, uid: string | null) {
  return useQuery({
    queryKey: [...grafanaKeys.all(scope), "embed", uid] as const,
    queryFn: () => staffRequest<GrafanaEmbed>(`${grafanaBase(scope)}/dashboards/${encodeURIComponent(uid ?? "")}/embed`),
    enabled: uid !== null,
    gcTime: 0,
  });
}

export function renderPath(scope: AnalyticsScope, uid: string, theme: "light" | "dark") {
  return `${grafanaBase(scope)}/dashboards/${encodeURIComponent(uid)}/render?width=1600&height=900&theme=${theme}`;
}

function useInvalidate(scope: AnalyticsScope) {
  const queryClient = useQueryClient();
  return () => Promise.all([
    queryClient.invalidateQueries({ queryKey: analyticsKeys.all(scope) }),
    queryClient.invalidateQueries({ queryKey: ["audit"] }),
  ]);
}

export function useGrafanaMutations(scope: AnalyticsScope) {
  const invalidate = useInvalidate(scope);
  const base = grafanaBase(scope);
  const update = useMutation({
    mutationFn: (changes: GrafanaConnectionPatch) => staffRequest<GrafanaConnection>(
      `${base}/connection`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: invalidate,
  });
  const setToken = useMutation({
    mutationFn: (token: string) => staffRequest<GrafanaConnection>(
      `${base}/token`, { method: "POST", body: JSON.stringify({ token }) }),
    onSuccess: invalidate,
  });
  const revokeToken = useMutation({
    mutationFn: () => staffRequest<void>(`${base}/token`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  const test = useMutation({
    mutationFn: () => staffRequest<GrafanaTestResult>(`${base}/test`, { method: "POST" }),
    onSettled: () => { void invalidate(); },
  });
  return { update, setToken, revokeToken, test };
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

const bundleName = (scope: AnalyticsScope, ext: string) =>
  `spaceworks-grafana-${scope.kind === "platform" ? "platform" : `space-${scope.makerspaceId}`}.${ext}`;

/** The provisioning bundle as a zip. It never carries the database password. */
export async function downloadGrafanaBundle(scope: AnalyticsScope) {
  saveBlob(await staffRequestBlob(`${grafanaBase(scope)}/bundle?archive=zip`), bundleName(scope, "zip"));
}

/** Right after the login is created or rotated: the JSON bundle with the shown-once password
 *  filled in here, in the browser. The password is never sent back to the server. */
export async function downloadGrafanaBundleWithPassword(scope: AnalyticsScope, password: string) {
  const bundle = await staffRequest<GrafanaBundle>(`${grafanaBase(scope)}/bundle`);
  for (const source of bundle.datasource.datasources ?? []) {
    source.secureJsonData = { ...(source.secureJsonData ?? {}), password };
  }
  saveBlob(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }), bundleName(scope, "json"));
}
