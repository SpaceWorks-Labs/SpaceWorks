import { useMemo } from "react";
import { privateKey, usePrivateCommand, usePrivateQuery, type EventScope } from "../../events/stagedForms/privateQueries";
import type { Page } from "../../events/stagedForms/types";
import { toClaimReview, toClaimRow, toProgramme, toRequestRow } from "./adapters";
import type { AllocationCommand, AttendanceCommand, AwardCommand, ClaimQueueRow, ClaimReviewDetail, CorrectDecisionCommand,
  DeadlineCommand, DecisionCommand, ProgrammeCommand, ProgrammeDetail, RecommendationCommand, RequestReviewRow } from "./types";
export const reimbursementAdminKey = (scope: EventScope) => privateKey("event-reimbursements", scope, true);
export const reimbursementAdminPath = (scope: EventScope) => `/admin/events/${scope.eventId}/reimbursements/`;

/** Read the server shape and hand components the adapted view model (see `adapters.ts`). */
function useAdapted<Raw, View>(key: readonly unknown[], path: string, adapt: (raw: Raw) => View) {
  const query = usePrivateQuery<Raw>(key, path, true);
  const data = useMemo(() => (query.data === undefined ? undefined : adapt(query.data)), [query.data, adapt]);
  return { ...query, data };
}
const pageOf = <Raw, View>(adapt: (raw: Raw) => View) => (raw: Page<Raw>): Page<View> => ({ ...raw, results: raw.results.map(adapt) });
const requestPage = pageOf(toRequestRow);
const claimPage = pageOf(toClaimRow);

export function useRequestQueue(scope: EventScope, page: number) {
  return useAdapted<Page<Parameters<typeof toRequestRow>[0]>, Page<RequestReviewRow>>([...reimbursementAdminKey(scope), "requests", page],
    `${reimbursementAdminPath(scope)}requests/?page=${page}`, requestPage);
}
export function useClaimQueue(scope: EventScope, page: number) {
  return useAdapted<Page<Parameters<typeof toClaimRow>[0]>, Page<ClaimQueueRow>>([...reimbursementAdminKey(scope), "claims", page],
    `${reimbursementAdminPath(scope)}claims/?page=${page}`, claimPage);
}
export function useClaimReview(scope: EventScope, id: number) {
  return useAdapted<Parameters<typeof toClaimReview>[0], ClaimReviewDetail>([...reimbursementAdminKey(scope), "claim", id],
    `${reimbursementAdminPath(scope)}claims/${id}/`, toClaimReview);
}
export function useProgramme(scope: EventScope) {
  return useAdapted<Parameters<typeof toProgramme>[0], ProgrammeDetail>([...reimbursementAdminKey(scope), "programme"],
    `${reimbursementAdminPath(scope)}programme/`, toProgramme);
}
export const useAwardCommand = (scope: EventScope) => usePrivateCommand<AwardCommand>(reimbursementAdminKey(scope), true);
export const useClaimReviewCommand = (scope: EventScope) => usePrivateCommand<RecommendationCommand | DecisionCommand | CorrectDecisionCommand | DeadlineCommand | AttendanceCommand | AllocationCommand>(reimbursementAdminKey(scope), true);
export const useProgrammeCommand = (scope: EventScope) => usePrivateCommand<ProgrammeCommand>(reimbursementAdminKey(scope), true);
