import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { HostingInvoice } from "../platformSpaces/plansApi";

export type PlanLevel = "ok" | "warning" | "limit";
export type SpacePlanUsage = {
  plan: { key: string; name: string; description: string } | null;
  trial_ends_at: string | null;
  read_only_reason: string | null;
  resources: UsageRow[];
  warnings: string[];
  /** Decision 236: false for an own space (no plan, nothing limited). */
  hosted?: boolean;
  /** Decisions 281/284 (every space, own or hosted): platform-credential use and the monthly space quotas. */
  platform_resources?: UsageRow[];
  space_quota_resources?: UsageRow[];
  /** Whether the platform's credentials may serve this space when it has none of its own (default on). */
  platform_switches?: Partial<Record<PlatformSwitch, boolean>>;
};
export type UsageRow = { key: string; label: string; used: number | null; limit: number | null;
  unit: "bytes" | "count" | "amount" | "per_minute" | (string & {}); percent: number | null; level: PlanLevel; area?: string };
export type PlatformSwitch = "email" | "sms" | "whatsapp" | "native_push" | "wallet";
export const spacePlanKey = (makerspaceId: number) => ["space-hosting-plan", makerspaceId] as const;

export function useSpacePlanUsage(makerspaceId: number, enabled: boolean) {
  return useQuery({ queryKey: spacePlanKey(makerspaceId), enabled,
    queryFn: () => staffRequest<SpacePlanUsage>(`/admin/makerspace/${makerspaceId}/hosting-plan`), refetchInterval: 5 * 60_000 });
}

export function useSpaceInvoices(makerspaceId: number, enabled: boolean) {
  return useQuery({ queryKey: ["space-hosting-invoices", makerspaceId], enabled,
    queryFn: () => staffRequest<HostingInvoice[]>(`/admin/makerspace/${makerspaceId}/hosting-invoices`) });
}

/** Online payment hands the browser to the provider's hosted checkout. */
export function useInvoiceCheckout(makerspaceId: number) {
  return useMutation({
    mutationFn: (invoiceId: number) => staffRequest<{ url: string }>(`/admin/makerspace/${makerspaceId}/hosting-invoices/${invoiceId}/checkout`,
      { method: "POST", body: "{}" }),
    onSuccess: ({ url }) => window.location.assign(url),
  });
}
