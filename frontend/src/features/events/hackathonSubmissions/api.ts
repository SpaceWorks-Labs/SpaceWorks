import { sessionScope, useClearDeniedQuery } from '../../staff/eventProgramme/sessionScope';
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import type { Submission, SubmissionScope, Project } from "./types";

export const submissionKey = (scope: SubmissionScope) => ["member", scope.accountId, "event-submission",
  scope.makerspaceId, scope.eventId, scope.teamId, ...sessionScope()] as const;
export const memberBase = (scope: SubmissionScope) => `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/`;
export const teamBase = (scope: SubmissionScope) => `${memberBase(scope)}teams/${scope.teamId}/`;

export function useSubmission(scope: SubmissionScope) {
  const query = useQuery({ queryKey: submissionKey(scope), queryFn: () => memberRequest<Submission>(`${teamBase(scope)}submission/`), retry: false, gcTime: 0, staleTime: 0 });
  const denied = useClearDeniedQuery(query.error, submissionKey(scope));
  return { ...query, data: denied ? undefined : query.data };
}

export function useSubmissionCommand(scope: SubmissionScope) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ action, version, project, operationId, stageId }: {
    action: "save" | "submit" | "withdraw"; version: number; project?: Partial<Project>; operationId: string; stageId?: number;
  }) => memberRequest<Submission>(`${teamBase(scope)}submission/${action === "save" ? "" : `${action}/`}`, {
    method: action === "save" ? "PATCH" : "POST", headers: { "Idempotency-Key": operationId },
    body: JSON.stringify({ operation_id: operationId, expected_version: version, ...project,
      ...(action === "submit" && stageId ? { stage_id: stageId } : {}) }),
  }), onSuccess: () => client.invalidateQueries({ queryKey: submissionKey(scope) }) });
}
