import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";
export const programmePath = (event: number) => `/admin/events/${event}/programme/`;
export const programmeKey = (event: number) => ["event-programme", event] as const;
export type Readiness = import('../../../generated/api').Readiness;
export type Live = import('../../../generated/api').Live;
export type Publishing = import('../../../generated/api').Publishing;
export function useProgrammeQuery<T>(event: number, section: string, polling = false) {
  const key = [...programmeKey(event), section, ...sessionScope()];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<T>(`${programmePath(event)}${section}/`), retry: false, gcTime: 0, staleTime: 0, refetchInterval: polling ? 15000 : false });
  const denied = useClearDeniedQuery(query.error, key);
  return { ...query, data: denied ? undefined : query.data };
}
export function usePublishingSave(event: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: Partial<Publishing> & { operation_id: string; expected_version: number; release_saved_website?: boolean }) => staffRequest<Publishing>(`${programmePath(event)}publishing/`, { method: "PATCH", headers: { "Idempotency-Key": body.operation_id }, body: JSON.stringify(body) }),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: programmeKey(event) }), client.invalidateQueries({ queryKey: ["event", event] })]) });
}
