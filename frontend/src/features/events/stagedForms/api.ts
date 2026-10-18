import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import type { CommandResult, Page, StageAssignment, StageResponse, StageScope } from "./types";

export const stageKey = (scope: StageScope) => ["event-stages", window.location.host, scope.actorId, scope.makerspaceId, scope.eventId] as const;
export const stagePath = (scope: StageScope) => `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}`;
export function useStageAssignments(scope: StageScope, page: number) {
  return useQuery({ queryKey: [...stageKey(scope), "assignments", page], gcTime: 0, retry: false,
    queryFn: () => memberRequest<Page<StageAssignment>>(`${stagePath(scope)}/stage-forms/?page=${page}`, { cache: "no-store" }) });
}
export function useStageResponse(scope: StageScope, responseId: number) {
  return useQuery({ queryKey: [...stageKey(scope), "response", responseId], gcTime: 0, retry: false,
    queryFn: () => memberRequest<StageResponse>(`${stagePath(scope)}/stage-responses/${responseId}/`, { cache: "no-store" }),
    refetchOnWindowFocus: false });
}
export function useStageCommand(scope: StageScope, responseId: number) {
  const client = useQueryClient();
  const pending = useRef<{ body: string; operation: string } | null>(null);
  return useMutation({ retry: false, gcTime: 0,
    mutationFn: async (payload: { submit: boolean; body: Record<string, unknown> }) => {
      const encoded = JSON.stringify(payload);
      if (pending.current?.body !== encoded) pending.current = { body: encoded, operation: crypto.randomUUID() };
      const operation = pending.current.operation;
      return memberRequest<CommandResult>(`${stagePath(scope)}/stage-responses/${responseId}/${payload.submit ? "submit/" : ""}`, {
        method: payload.submit ? "POST" : "PUT", cache: "no-store", headers: { "Idempotency-Key": operation },
        body: JSON.stringify({ ...payload.body, operation_id: operation }),
      });
    }, onSuccess: async () => { pending.current = null; await client.invalidateQueries({ queryKey: stageKey(scope) }); } });
}
