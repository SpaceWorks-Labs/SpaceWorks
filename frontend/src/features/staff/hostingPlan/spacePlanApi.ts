import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { HostingInvoice } from "../platformSpaces/plansApi";

export type PlanLevel = "ok" | "warning" | "limit";
export type SpacePlanUsage = {
  plan: { key: string; name: string; description: string } | null;
  trial_ends_at: string | null;
  read_only_reason: string | null;
  resources: { key: string; label: string; used: number | null; limit: number | null; unit: "bytes" | "count"; percent: number | null; level: PlanLevel }[];
  warnings: string[];
};

export function useSpacePlanUsage(makerspaceId: number, enabled: boolean) {
  return useQuery({ queryKey: ["space-hosting-plan", makerspaceId], enabled,
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
