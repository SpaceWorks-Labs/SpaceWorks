import { useQuery } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import type { ReportChartSpec } from "../staff/panels/analyticsApi";
import type { ChartRecord } from "../staff/panels/charts/chartSpec";

export type MemberUsageSeries = { rows: ChartRecord[]; chart_spec: ReportChartSpec };
/** Matches MemberUsageSerializer; payments remain independent of usage_available. */
export type MemberUsage = {
  usage_available: boolean;
  loans?: { count: number; returned_count: number; currently_out: number; monthly: MemberUsageSeries };
  machines?: { hours: string; monthly: MemberUsageSeries; top_machines: MemberUsageSeries };
  bookings?: { count: number; monthly: MemberUsageSeries };
  events?: { attended_count: number; chart: MemberUsageSeries };
  payments?: { paid_by_currency: Record<string, string>; outstanding_by_currency: Record<string, string>; totals: MemberUsageSeries };
};
export const memberUsageKey = (id: number) => ["member", "my-usage", id] as const;
export function useMemberUsage(id: number) {
  return useQuery({ queryKey: memberUsageKey(id), queryFn: () => memberRequest<MemberUsage>(`/member/makerspaces/${id}/my-usage`),
    enabled: id >= 0, retry: false });
}
