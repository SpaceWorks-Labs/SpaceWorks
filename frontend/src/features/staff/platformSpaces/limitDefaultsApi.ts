import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { LimitArea } from "./limitsApi";

// Hand-written until the OpenAPI snapshot is regenerated (decision 328a).
const PATH = "/admin/platform/limit-defaults";
export type LimitDefaultRow = {
  key: string; label: string; unit: "count" | "bytes"; module: string; group: string;
  /** The platform default for this key; null = none (unlimited, the default). */
  default: number | null;
};
export type LimitDefaults = { groups: LimitArea[]; rows: LimitDefaultRow[] };

export const limitDefaultsKey = ["platform-limit-defaults"] as const;

export function useLimitDefaults() {
  return useQuery({ queryKey: limitDefaultsKey, retry: false,
    queryFn: () => staffRequest<LimitDefaults>(PATH, {}, "platform") });
}

/** Set (a number) or clear (null) the platform default of some keys; the server audits the change. */
export function useSaveLimitDefaults() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (defaults: Record<string, number | null>) =>
      staffRequest<LimitDefaults>(PATH, { method: "PUT", body: JSON.stringify({ defaults }) }, "platform"),
    onSuccess: (data) => {
      client.setQueryData(limitDefaultsKey, data);
      void client.invalidateQueries({ queryKey: ["platform-space-limits"] });
      void client.invalidateQueries({ queryKey: ["platform-space-health"] });
    },
  });
}
