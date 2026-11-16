import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";

export type ShortLinkVisitDay = { day: string; count: number };
export type ShortLink = {
  code: string | null;
  url: string | null;
  created_at: string | null;
  visits_30d: ShortLinkVisitDay[];
  total_visits: number;
};

const path = (eventId: number) => `/admin/events/${eventId}/short-link/`;
export const shortLinkKey = (eventId: number) => ["event-short-link", eventId] as const;

/** Server state for one event's short link; `private, no-store` on the server, refetched on mount. */
export function useShortLink(eventId: number, enabled = true) {
  return useQuery({ queryKey: shortLinkKey(eventId), enabled, retry: false, staleTime: 0,
    queryFn: () => staffRequest<ShortLink>(path(eventId)) });
}

export function useCreateShortLink(eventId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => staffRequest<ShortLink>(path(eventId), { method: "POST" }),
    onSuccess: data => client.setQueryData(shortLinkKey(eventId), data),
  });
}

export function useRegenerateShortLink(eventId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => staffRequest<ShortLink>(`${path(eventId)}regenerate/`,
      { method: "POST", body: JSON.stringify({ confirm: true }) }),
    onSuccess: data => client.setQueryData(shortLinkKey(eventId), data),
  });
}
