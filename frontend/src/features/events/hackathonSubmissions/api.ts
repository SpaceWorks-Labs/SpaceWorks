import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import type { Submission, SubmissionScope, Project } from "./types";

export const submissionKey = (scope: SubmissionScope) => ["member", scope.accountId, "event-submission",
  scope.makerspaceId, scope.eventId, scope.teamId] as const;
export const memberBase = (scope: SubmissionScope) => `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/`;
export const teamBase = (scope: SubmissionScope) => `${memberBase(scope)}teams/${scope.teamId}/`;

export function useSubmission(scope: SubmissionScope) {
  return useQuery({ queryKey: submissionKey(scope), queryFn: () => memberRequest<Submission>(`${teamBase(scope)}submission/`), retry: false });
}

export function useSubmissionCommand(scope: SubmissionScope) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ action, version, project, operationId }: {
    action: "save" | "submit" | "withdraw"; version: number; project?: Partial<Project>; operationId: string;
  }) => memberRequest<Submission>(`${teamBase(scope)}submission/${action === "save" ? "" : `${action}/`}`, {
    method: action === "save" ? "PATCH" : "POST",
    body: JSON.stringify({ operation_id: operationId, expected_version: version, ...project }),
  }), onSuccess: () => client.invalidateQueries({ queryKey: submissionKey(scope) }) });
}
