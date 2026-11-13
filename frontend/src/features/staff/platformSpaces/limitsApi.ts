import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";

// Hand-written until the OpenAPI snapshot is regenerated (decision 234).
const P = "/admin/platform";
export type HostingSwitch = { enabled: boolean; forced_by_environment: boolean };
export type LimitSource = "own" | "override" | "plan" | "default" | "unlimited";
export type LimitRow = {
  key: string; label: string; unit: "bytes" | "count"; effective: number | null;
  source: LimitSource; override: number | null; has_override: boolean; used: number | null;
  /** A built-in value shown as "Suggested: N" next to an empty field; never enforced (#236). */
  suggested?: number | null;
  /** Decision 328a: the module group (heading of the module switch screens), its owning module and the platform default. */
  group?: string; module?: string; platform_default?: number | null;
};
export type HostingType = "own" | "hosted";
export type LimitLevel = "ok" | "warning" | "limit";
/** Decisions 281/284: the monthly platform-credential and space-quota rows (`limit` null = no limit, the default). */
export type UsageLimitRow = {
  key: string; label: string; unit: "count" | "amount" | "bytes" | "per_minute" | (string & {}); limit: number | null; used: number | null;
  percent: number | null; level?: LimitLevel; area?: string; group?: string; module?: string; platform_default?: number | null;
};
export type LimitArea = { key: string; label: string };
export type SpaceLimits = { custom_domain: boolean; rows: (LimitRow & { area?: string })[]; hosting_type?: HostingType; hosting_active?: boolean; hosted?: boolean;
  /** Console groups in order, translated by the server. */
  areas?: LimitArea[];
  /** Module groups in the module switch screens' order (decision 328a); preferred over `areas`. */
  groups?: LimitArea[]; platform_rows?: UsageLimitRow[]; quota_rows?: UsageLimitRow[] };
export type BulkLimitsBody = { makerspace_ids: number[]; set: Record<string, number | null>; clear: string[] };
export type SpaceHostingType = { hosting_type: HostingType; hosting_active: boolean; hosted: boolean };
export type RequestRate = { scope: string; default: string; rate: string; overridden: boolean; min_rate: string; max_rate: string; env_key: string };

export const switchKey = ["platform-hosting-switch"] as const;
export const ratesKey = ["platform-request-limits"] as const;
export const limitsKey = (id: number) => ["platform-space-limits", id] as const;

export function useHostingSwitch() {
  return useQuery({ queryKey: switchKey, queryFn: () => staffRequest<HostingSwitch>(`${P}/hosting-switch`, {}, "platform") });
}
export function useSetHostingSwitch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => staffRequest<HostingSwitch>(`${P}/hosting-switch`, { method: "PUT", body: JSON.stringify({ enabled }) }, "platform"),
    onSuccess: (data) => {
      client.setQueryData(switchKey, data);
      void client.invalidateQueries({ queryKey: ["public-config"] });
    },
  });
}
export function useSpaceLimits(id: number, enabled = true) {
  return useQuery({ queryKey: limitsKey(id), enabled: enabled && id > 0, retry: false,
    queryFn: () => staffRequest<SpaceLimits>(`${P}/spaces/${id}/limits`, {}, "platform") });
}
export function useSaveSpaceLimits(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (overrides: Record<string, number | boolean | null>) =>
      staffRequest<SpaceLimits>(`${P}/spaces/${id}/limits`, { method: "PUT", body: JSON.stringify({ overrides }) }, "platform"),
    onSuccess: (data) => client.setQueryData(limitsKey(id), data),
  });
}
/** Set or clear the same keys on up to 50 spaces, all or nothing (409 `bulk_failed` names the refused space). */
export function useBulkSpaceLimits() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkLimitsBody) => staffRequest<{ updated: number; makerspace_ids: number[] }>(`${P}/spaces/limits-bulk`,
      { method: "POST", body: JSON.stringify(body) }, "platform"),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["platform-space-limits"] });
      void client.invalidateQueries({ queryKey: ["platform-space-health"] });
    },
  });
}
export function useRequestRates() {
  return useQuery({ queryKey: ratesKey, queryFn: () => staffRequest<RequestRate[]>(`${P}/request-limits`, {}, "platform") });
}
export function useSaveRequestRate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ scope, rate }: { scope: string; rate: string | null }) => staffRequest<RequestRate>(`${P}/request-limits/${scope}`,
      rate === null ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ rate }) }, "platform"),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ratesKey }); },
  });
}

export const hostingTypeKey = (id: number) => ["platform-space-hosting-type", id] as const;
export function useSpaceHostingType(id: number) {
  return useQuery({ queryKey: hostingTypeKey(id), retry: false,
    queryFn: () => staffRequest<SpaceHostingType>(`${P}/spaces/${id}/hosting-type`, {}, "platform") });
}
/** Decision 236: own space (unlimited) or hosted space (plans, limits, billing). Audited server-side. */
export function useSetSpaceHostingType(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (hosting_type: HostingType) => setSpaceHostingType(id, hosting_type),
    onSuccess: (data) => {
      client.setQueryData(hostingTypeKey(id), data);
      void client.invalidateQueries({ queryKey: limitsKey(id) });
      void client.invalidateQueries({ queryKey: ["platform-space-health"] });
    },
  });
}
export const setSpaceHostingType = (id: number, hosting_type: HostingType) =>
  staffRequest<SpaceHostingType>(`${P}/spaces/${id}/hosting-type`, { method: "PUT", body: JSON.stringify({ hosting_type }) }, "platform");
