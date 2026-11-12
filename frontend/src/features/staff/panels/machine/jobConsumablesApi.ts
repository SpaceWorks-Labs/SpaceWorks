import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../lib/api";
import type { ConsumableEntry } from "../../../machine-consumables/entries";
import type { ConsumableDefinition } from "./typeWizard/consumablesApi";

/** One recorded amount of a profile consumable on a job (decision 341). */
export type ConsumableUsage = { id: number; key: string; name: string; kind: string; unit: string; phase: "estimate" | "actual"; quantity: string;
  attributes: Record<string, string>; source: string; unit_price: string | null; created_at: string };
export type JobConsumables = { profile: ConsumableDefinition[]; estimates: ConsumableUsage[]; actuals: ConsumableUsage[]; missing_required: string[] };

const path = (makerspaceId: number, jobId: number) => `/admin/makerspaces/${makerspaceId}/machine-jobs/${jobId}/consumables`;
export const jobConsumablesKey = (makerspaceId: number, jobId: number) => ["machine-job-consumables", makerspaceId, jobId] as const;

export function useJobConsumables(makerspaceId: number, jobId: number, enabled = true) {
  return useQuery({ queryKey: jobConsumablesKey(makerspaceId, jobId), enabled, retry: false, queryFn: () => staffRequest<JobConsumables>(path(makerspaceId, jobId)) });
}

export function useRecordJobConsumables(makerspaceId: number, jobId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: { phase: "estimate" | "actual"; entries: ConsumableEntry[] }) =>
    staffRequest<JobConsumables>(path(makerspaceId, jobId), { method: "POST", body: JSON.stringify(body) }),
  onSuccess: data => client.setQueryData(jobConsumablesKey(makerspaceId, jobId), data) });
}
