import { privateKey, usePrivateCommand, usePrivateQuery } from "./privateQueries";
import type { CommandResult, Page, StageAssignment, StageResponse, StageScope } from "./types";
import type { stagePayload } from "./formPayload";

export const stageKey = (scope: StageScope) => privateKey("event-stages", scope);
export const stagePath = (scope: StageScope) => `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}`;
export function useStageAssignments(scope: StageScope, page: number) {
  return usePrivateQuery<Page<StageAssignment>>([...stageKey(scope), "assignments", page], `${stagePath(scope)}/stage-forms/?page=${page}`);
}
export function useStageResponse(scope: StageScope, responseId: number) {
  return usePrivateQuery<StageResponse>([...stageKey(scope), "response", responseId], `${stagePath(scope)}/stage-responses/${responseId}/`);
}
export type StageAnswerCommand = ReturnType<typeof stagePayload> & { expected_version: number; expected_assignment_version: number };
export function useStageCommand(scope: StageScope) {
  return usePrivateCommand<StageAnswerCommand, CommandResult>(stageKey(scope));
}
