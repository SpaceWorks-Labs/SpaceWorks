import { privateKey, usePrivateCommand, usePrivateQuery, type EventScope } from "../../events/stagedForms/privateQueries";
import type { Page, StageResponse } from "../../events/stagedForms/types";
import type { AssignmentCommand, StageCommand, StageDefinition, StageDefinitionSummary, ManagedAssignment, ActivationCommand, ActivationResult } from "./types";
export const stageAdminKey = (scope: EventScope) => privateKey("event-stages", scope, true);
export const stageAdminPath = (scope: EventScope) => `/admin/events/${scope.eventId}/`;
export function useStageDefinitions(scope: EventScope, page: number) {
  return usePrivateQuery<Page<StageDefinitionSummary>>([...stageAdminKey(scope), "definitions", page], `${stageAdminPath(scope)}stage-forms/?page=${page}`, true);
}
export function useStageDefinition(scope: EventScope, id?: number) {
  return usePrivateQuery<StageDefinition>([...stageAdminKey(scope), "definition", id], `${stageAdminPath(scope)}stage-forms/${id}/`, true, Boolean(id));
}
export function useManagedAssignments(scope: EventScope, page: number) {
  return usePrivateQuery<Page<ManagedAssignment>>([...stageAdminKey(scope), "assignments", page], `${stageAdminPath(scope)}stage-assignments/?page=${page}`, true);
}
export function useStaffStageResponse(scope: EventScope, id: number, finance: boolean, revision?: number) {
  return usePrivateQuery<StageResponse>([...stageAdminKey(scope), "response", id, finance ? "finance" : "organizer", revision ?? "current"],
    `${stageAdminPath(scope)}stage-responses/${id}/${finance ? "finance/" : ""}${revision ? `?revision=${revision}` : ""}`, true);
}
export const useDefinitionCommand = (scope: EventScope) => usePrivateCommand<StageCommand>(stageAdminKey(scope), true);
export const useAssignmentCommand = (scope: EventScope) => usePrivateCommand<AssignmentCommand>(stageAdminKey(scope), true);
export const useActivationCommand = (scope: EventScope) => usePrivateCommand<ActivationCommand, ActivationResult>(stageAdminKey(scope), true);
export const useMilestoneCommand = (scope: EventScope) => usePrivateCommand<{ expected_version: number; participant_ids: number[]; published: boolean; reason_code: string }>(stageAdminKey(scope), true);
