import { useQuery } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import type { MemberUsage } from "../../generated/api";
export type { MemberUsage, MemberUsageSeries } from "../../generated/api";

export const memberUsageKey = (id: number) => ["member", "my-usage", id] as const;
export function useMemberUsage(id: number) {
  return useQuery({ queryKey: memberUsageKey(id), queryFn: () => memberRequest<MemberUsage>(`/member/makerspaces/${id}/my-usage`),
    enabled: id >= 0, retry: false });
}
