import { privateKey, usePrivateCommand, usePrivateQuery, type EventScope } from "../../events/stagedForms/privateQueries";
import type { Page } from "../../events/stagedForms/types";
import type { AllocationCommand, AttendanceCommand, AwardCommand, ClaimQueueRow, ClaimReviewDetail, CorrectDecisionCommand,
  DeadlineCommand, DecisionCommand, ProgrammeCommand, ProgrammeDetail, RecommendationCommand, RequestReviewRow } from "./types";
export const reimbursementAdminKey = (scope: EventScope) => privateKey("event-reimbursements", scope, true);
export const reimbursementAdminPath = (scope: EventScope) => `/admin/events/${scope.eventId}/reimbursements/`;
export function useRequestQueue(scope: EventScope, page: number) {
  return usePrivateQuery<Page<RequestReviewRow>>([...reimbursementAdminKey(scope), "requests", page], `${reimbursementAdminPath(scope)}requests/?page=${page}`, true);
}
export function useClaimQueue(scope: EventScope, page: number) {
  return usePrivateQuery<Page<ClaimQueueRow>>([...reimbursementAdminKey(scope), "claims", page], `${reimbursementAdminPath(scope)}claims/?page=${page}`, true);
}
export function useClaimReview(scope: EventScope, id: number) {
  return usePrivateQuery<ClaimReviewDetail>([...reimbursementAdminKey(scope), "claim", id], `${reimbursementAdminPath(scope)}claims/${id}/`, true);
}
export function useProgramme(scope: EventScope) {
  return usePrivateQuery<ProgrammeDetail>([...reimbursementAdminKey(scope), "programme"], `${reimbursementAdminPath(scope)}programme/`, true);
}
export const useAwardCommand = (scope: EventScope) => usePrivateCommand<AwardCommand>(reimbursementAdminKey(scope), true);
export const useClaimReviewCommand = (scope: EventScope) => usePrivateCommand<RecommendationCommand | DecisionCommand | CorrectDecisionCommand | DeadlineCommand | AttendanceCommand | AllocationCommand>(reimbursementAdminKey(scope), true);
export const useProgrammeCommand = (scope: EventScope) => usePrivateCommand<ProgrammeCommand>(reimbursementAdminKey(scope), true);
