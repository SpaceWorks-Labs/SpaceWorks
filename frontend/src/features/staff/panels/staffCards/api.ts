import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { CardDesign } from "../../../../components/card-designer/cardTypes";
import { staffRequest } from "../../../../lib/api";
import type { BulkIssueResult, StaffCardFilter, StaffCardPage, StaffCardSettings, StaffCardSummary } from "./types";

const space = (id: number) => `/admin/makerspaces/${id}`;
export const staffCardJobsPath = (id: number) => `${space(id)}/staff-card-jobs`;
export const staffCardKeys = {
  all: (id: number) => ["staff-cards", id] as const,
  list: (id: number, q: string, card: StaffCardFilter, page: number) => ["staff-cards", id, "list", q, card, page] as const,
  settings: (id: number) => ["staff-cards", id, "settings"] as const,
  design: (id: number) => ["staff-cards", id, "design"] as const,
};

export function useStaffCards(makerspaceId: number, q: string, card: StaffCardFilter, page: number) {
  const params = new URLSearchParams({ page: String(page) });
  if (q.trim()) params.set("q", q.trim());
  if (card !== "all") params.set("card", card);
  return useQuery({
    queryKey: staffCardKeys.list(makerspaceId, q, card, page), placeholderData: (previous) => previous,
    queryFn: () => staffRequest<StaffCardPage>(`${space(makerspaceId)}/staff-cards?${params}`),
  });
}

/** Every write refreshes the whole list family: a revoke moves a person between the live and no-card filters. */
function useCardWrite<Vars, Out>(makerspaceId: number, run: (vars: Vars) => Promise<Out>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: run, onSuccess: () => client.invalidateQueries({ queryKey: staffCardKeys.all(makerspaceId) }) });
}

export const useIssueStaffCard = (makerspaceId: number) => useCardWrite(makerspaceId, (membershipId: number) =>
  staffRequest<StaffCardSummary>(`${space(makerspaceId)}/staff-cards`, { method: "POST", body: JSON.stringify({ membership_id: membershipId }) }));

export const useBulkIssueStaffCards = (makerspaceId: number) => useCardWrite(makerspaceId, (membershipIds: number[]) =>
  staffRequest<BulkIssueResult>(`${space(makerspaceId)}/staff-cards/bulk-issue`,
    { method: "POST", body: JSON.stringify({ membership_ids: membershipIds }) }));

export const useReissueStaffCard = (makerspaceId: number) => useCardWrite(makerspaceId, (cardId: number) =>
  staffRequest<StaffCardSummary>(`/admin/staff-cards/${cardId}/reissue`, { method: "POST" }));

export const useRevokeStaffCard = (makerspaceId: number) => useCardWrite(makerspaceId, ({ cardId, reason }: { cardId: number; reason: string }) =>
  staffRequest<StaffCardSummary>(`/admin/staff-cards/${cardId}/revoke`, { method: "POST", body: JSON.stringify(reason ? { reason } : {}) }));

export function useStaffCardSettings(makerspaceId: number) {
  return useQuery({ queryKey: staffCardKeys.settings(makerspaceId),
    queryFn: () => staffRequest<StaffCardSettings>(`${space(makerspaceId)}/staff-cards/settings`) });
}

export function useSaveStaffCardSettings(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { prefix: string; pattern: string }) => staffRequest<StaffCardSettings>(
      `${space(makerspaceId)}/staff-cards/settings`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (saved) => client.setQueryData(staffCardKeys.settings(makerspaceId), saved),
  });
}

export function useStaffCardDesign(makerspaceId: number) {
  return useQuery({ queryKey: staffCardKeys.design(makerspaceId),
    queryFn: () => staffRequest<CardDesign>(`${space(makerspaceId)}/staff-card-design`) });
}
