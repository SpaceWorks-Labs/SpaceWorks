import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { eventKeys, type Paginated } from "./eventsApiTypes";
import { eventStaffGrantKeys } from "./eventStaffGrantsApi";

/** Hand-typed from the Phase 2 events contract (`admin/events/{id}/speakers/`). */
export type EventSpeaker = {
  id: number; event_id: number; display_name: string;
  user: { id: number; display_name: string } | null;
  /** The website speaker section this speaker is linked to, if any. */
  section_slug: string | null;
  status: "linked" | "invited" | "removed";
  linked_via: "staff_assigned" | "claimed" | "";
  /** The speaker also holds a check_in staff grant (the "Speaker" preset). */
  grants_check_in: boolean;
  claim_expires_at: string | null; claimed_at: string | null;
  created_at: string; removed_at: string | null;
};
export type SpeakerCandidate = { id: number; display_name: string; username: string; relation: "member" | "staff" | "registrant" };
export type AssignSpeakerInput = { user_id: number; display_name?: string; section_slug?: string; grant_check_in?: boolean };
export type InviteSpeakerInput = { display_name: string; section_slug?: string; grant_check_in?: boolean };

export const eventSpeakerKeys = {
  all: (eventId: number) => [...eventKeys.detail(eventId), "speakers"] as const,
  page: (eventId: number, page: number) => [...eventKeys.detail(eventId), "speakers", page] as const,
  candidates: (eventId: number, term: string) => [...eventKeys.detail(eventId), "speaker-candidates", term] as const,
};

export function useEventSpeakers(eventId: number, page = 1) {
  return useQuery({ queryKey: eventSpeakerKeys.page(eventId, page),
    queryFn: () => staffRequest<Paginated<EventSpeaker>>(`/admin/events/${eventId}/speakers/?page=${page}`) });
}

/** The server answers nothing below two characters, so the browser does not ask. */
export function useSpeakerCandidates(eventId: number, term: string) {
  return useQuery({ queryKey: eventSpeakerKeys.candidates(eventId, term), enabled: term.length >= 2, staleTime: 30_000,
    queryFn: () => staffRequest<{ results: SpeakerCandidate[] }>(`/admin/events/${eventId}/speaker-candidates/?${new URLSearchParams({ search: term })}`) });
}

/** Assigning, inviting and removing all change the list; a speaker with check-in also changes the staff grants. */
function useSpeakerRefresh(eventId: number) {
  const client = useQueryClient();
  return () => Promise.all([
    client.invalidateQueries({ queryKey: eventSpeakerKeys.all(eventId) }),
    client.invalidateQueries({ queryKey: eventStaffGrantKeys.resource({ kind: "event", id: eventId }) }),
  ]);
}

export function useAssignSpeaker(eventId: number) {
  const refresh = useSpeakerRefresh(eventId);
  return useMutation({ onSuccess: refresh, mutationFn: (input: AssignSpeakerInput) =>
    staffRequest<EventSpeaker>(`/admin/events/${eventId}/speakers/`, { method: "POST", body: JSON.stringify(input) }) });
}

export function useInviteSpeaker(eventId: number) {
  const refresh = useSpeakerRefresh(eventId);
  return useMutation({ onSuccess: refresh, mutationFn: (input: InviteSpeakerInput) =>
    staffRequest<{ speaker: EventSpeaker; claim_url: string }>(`/admin/events/${eventId}/speakers/invite/`, { method: "POST", body: JSON.stringify(input) }) });
}

export function useRemoveSpeaker(eventId: number) {
  const refresh = useSpeakerRefresh(eventId);
  return useMutation({ onSuccess: refresh, mutationFn: (speakerId: number) =>
    staffRequest<EventSpeaker>(`/admin/event-speakers/${speakerId}/remove/`, { method: "POST", body: "{}" }) });
}
