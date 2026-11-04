import { privateKey, usePrivateCommand, usePrivateQuery, type CommonCommand } from "../stagedForms/privateQueries";
import { stagePath } from "../stagedForms/api";
import type { ClaimDetail, ClaimLine, ReimbursementOverview, ReimbursementScope, RequestSubmission } from "./types";
import type { stagePayload } from "../stagedForms/formPayload";
export const reimbursementKey = (scope: ReimbursementScope) => privateKey("event-reimbursements", scope);
export const reimbursementPath = (scope: ReimbursementScope) => `${stagePath(scope)}/reimbursement/`;
export function useReimbursement(scope: ReimbursementScope, creationOperationId?: string) {
  return usePrivateQuery<ReimbursementOverview>([...reimbursementKey(scope), "overview", creationOperationId ?? ""],
    `${reimbursementPath(scope)}${creationOperationId ? `?creation_operation_id=${encodeURIComponent(creationOperationId)}` : ""}`);
}
export function useClaim(scope: ReimbursementScope) {
  return usePrivateQuery<ClaimDetail>([...reimbursementKey(scope), "claim"], `${reimbursementPath(scope)}claim/`);
}
export type ApplicantCommand = CommonCommand & (
  { reimbursement_request: RequestSubmission } | { award_revision: number } | { current_revision: number | null; statement?: string } |
  { lines: ClaimLine[] } & Partial<ReturnType<typeof stagePayload>> | Record<never, never>);
export function useApplicantCommand(scope: ReimbursementScope) {
  return usePrivateCommand<ApplicantCommand>(reimbursementKey(scope));
}
