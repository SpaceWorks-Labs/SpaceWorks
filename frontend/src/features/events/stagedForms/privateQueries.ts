import { t } from "@lingui/core/macro";
import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, staffRequest, StructuredApiError } from "../../../lib/api";
import { sessionScope, useClearDeniedQuery } from "../../staff/eventProgramme/sessionScope";

export type EventScope = { actorId: number; makerspaceId: number; eventId: number };
export type CommonCommand = { expected_version: number };
export type CommandReply = { id: number; version: number; state: string };
export function privateKey(family: string, scope: EventScope, staff = false) {
  return [family, staff ? "staff" : "member", window.location.host, scope.actorId, scope.makerspaceId, scope.eventId, ...sessionScope()] as const;
}
export function usePrivateQuery<T>(key: readonly unknown[], path: string, staff = false, enabled = true) {
  const query = useQuery({ queryKey: key, enabled, gcTime: 0, retry: false, staleTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false,
    queryFn: () => (staff ? staffRequest : memberRequest)<T>(path, { cache: "no-store" }) });
  useClearDeniedQuery(query.error, key);
  // A failed refresh must never leave stale private answers visible.
  return { ...query, data: query.error ? undefined : query.data };
}
export function usePrivateCommand<T extends CommonCommand, R = CommandReply>(prefix: readonly unknown[], staff = false) {
  const client = useQueryClient();
  const pending = useRef<{ encoded: string; operation: string } | null>(null);
  return useMutation({ gcTime: 0, retry: false,
    mutationFn: async ({ path, body, method = "POST" }: { path: string; body: T; method?: "POST" | "PUT" | "PATCH" | "DELETE" }) => {
      const encoded = JSON.stringify({ path, body, method });
      if (pending.current?.encoded !== encoded) pending.current = { encoded, operation: crypto.randomUUID() };
      const operation = pending.current.operation;
      return (staff ? staffRequest : memberRequest)<R>(path, { method, cache: "no-store",
        headers: { "Idempotency-Key": operation }, body: JSON.stringify({ ...body, operation_id: operation }) });
    },
    onSuccess: () => { pending.current = null; void client.invalidateQueries({ queryKey: prefix }); },
    onError: error => {
      // Never render server error bodies: they may contain submitted personal values.
      if (error instanceof StructuredApiError && [401, 403, 404].includes(error.status)) {
        client.getQueryCache().findAll({ queryKey: prefix }).forEach(query => query.setState({ data: undefined }));
        client.removeQueries({ queryKey: prefix });
      }
    },
  });
}
export function commandError(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.code?.includes("reauth")) return t`Verify your session again, then retry this action.`;
    if ([401, 403, 404].includes(error.status)) return t`This content is no longer available for your access.`;
    if (error.code === "stage_incomplete") return t`Complete the required stage forms before continuing.`;
    if (error.code === "stage_age_question_unsupported") return t`Stage forms cannot ask for date of birth or age.`;
    if (error.status === 409) return t`This record changed. Reload and review the current version before trying again.`;
    if (error.status === 423) return t`Changes are paused for this record. Try again when it is available.`;
  }
  return t`The action did not complete. Check the fields and try again. Your edits are still here.`;
}
