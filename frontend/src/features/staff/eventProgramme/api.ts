import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";
export const programmePath = (event: number) => `/admin/events/${event}/programme/`;
export const programmeKey = (event: number) => ["event-programme", event] as const;
export type Readiness = { event_id: number; items: { code: string; status: "ready" | "missing" | "action" | "unavailable"; label: string; href: string; count: number | null }[] };
export type Live = { event_id: number; available_from: string; doors_open_at: string; seconds_until_doors: number; active: boolean; going: number; checked_in: number; arrivals: { starts_at: string; count: number }[]; first_run: boolean };
export type Publishing = { event_id: number; version: number; is_public: boolean; registration_audience: string; status: "draft" | "published" | "cancelled" | "completed"; website_released: boolean; website_revision: number | null };
export function useProgrammeQuery<T>(event: number, section: string, polling = false) {
  const key = [...programmeKey(event), section, ...sessionScope()];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<T>(`${programmePath(event)}${section}/`), refetchInterval: polling ? 15000 : false });
  const denied = useClearDeniedQuery(query.error, key);
  return { ...query, data: denied ? undefined : query.data };
}
export function usePublishingSave(event: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: Partial<Publishing> & { operation_id: string; expected_version: number; release_saved_website?: boolean }) => staffRequest<Publishing>(`${programmePath(event)}publishing/`, { method: "PATCH", headers: { "Idempotency-Key": body.operation_id }, body: JSON.stringify(body) }),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: programmeKey(event) }), client.invalidateQueries({ queryKey: ["event", event] })]) });
}
