import { privateKey, usePrivateCommand, usePrivateQuery, type CommonCommand } from "../stagedForms/privateQueries";
import { stagePath } from "../stagedForms/api";
import type { ClaimLine, ReimbursementOverview, ReimbursementScope, RequestSubmission } from "./types";
export const reimbursementKey = (scope: ReimbursementScope) => privateKey("event-reimbursements", scope);
export const reimbursementPath = (scope: ReimbursementScope) => `${stagePath(scope)}/reimbursement/`;
/** One read carries the request, award and claim (with its draft, revisions and decisions): `MemberSummary`. */
export function useReimbursement(scope: ReimbursementScope, creationOperationId?: string) {
  return usePrivateQuery<ReimbursementOverview>([...reimbursementKey(scope), "overview", creationOperationId ?? ""],
    `${reimbursementPath(scope)}${creationOperationId ? `?creation_operation_id=${encodeURIComponent(creationOperationId)}` : ""}`);
}
export type ApplicantCommand = CommonCommand & (
  { reimbursement_request: RequestSubmission } | { award_revision: number } | { current_revision: number | null; statement?: string } |
  { lines: ClaimLine[] } | Record<never, never>);
export function useApplicantCommand(scope: ReimbursementScope) {
  return usePrivateCommand<ApplicantCommand>(reimbursementKey(scope));
}
