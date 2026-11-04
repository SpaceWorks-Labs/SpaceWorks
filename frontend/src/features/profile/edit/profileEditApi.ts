import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberRequest, StructuredApiError } from "../../../lib/api";
import type { FamilyFlags, TimelineKind } from "../publicProfileApi";
import type { MemberProfile } from "../../members/memberProfile/types";

/** Hand-typed from the frozen Phase 1b member contract (profile_contract_views.py). */
export type TimelineEntry = {
  id: number; kind: TimelineKind; title: string; organization: string; location: string;
  start: string; end: string | null; description: string; order: number;
};
export type TimelineDraft = Omit<TimelineEntry, "id">;
export type PublicationPatch = Partial<FamilyFlags> & { public_visible?: boolean; publication_consent?: boolean };

// Shared with MemberProfilePanel so a handle or publication change refreshes the whole form.
export const memberProfileKey = (makerspaceId: number) => ["member", "profile-page", makerspaceId] as const;
export const timelineKey = (makerspaceId: number) => ["member", "profile-timeline", makerspaceId] as const;
const root = (makerspaceId: number) => `/member/makerspaces/${makerspaceId}/profile`;

/** The server's field message (handle grammar, reserved name, cooldown) beats a generic one. */
export function fieldError(error: unknown, field: string) {
  if (error instanceof StructuredApiError) {
    const value = error.body[field];
    const message = Array.isArray(value) ? value.filter(item => typeof item === "string").join(" ") : typeof value === "string" ? value : "";
    return message || error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}

function useRefresh(makerspaceId: number) {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: memberProfileKey(makerspaceId) });
}

export function useClaimHandle(makerspaceId: number) {
  const refresh = useRefresh(makerspaceId);
  return useMutation({
    mutationFn: (handle: string) => memberRequest<{ handle: string; claimed_at: string; changed_at: string }>(
      `${root(makerspaceId)}/handle`, { method: "POST", body: JSON.stringify({ handle }) }),
    onSuccess: refresh,
  });
}

export function useReleaseHandle(makerspaceId: number) {
  const refresh = useRefresh(makerspaceId);
  return useMutation({
    mutationFn: () => memberRequest<void>(`${root(makerspaceId)}/handle`, { method: "DELETE" }),
    onSuccess: refresh,
  });
}

export function usePatchPublication(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PublicationPatch) => memberRequest<MemberProfile>(root(makerspaceId), { method: "PATCH", body: JSON.stringify(body) }),
    // The response is the saved profile; write it straight into the cache, then reconcile.
    onSuccess: data => {
      client.setQueryData<MemberProfile>(memberProfileKey(makerspaceId), current => current ? { ...current, ...pickPublication(data) } : data);
      return client.invalidateQueries({ queryKey: memberProfileKey(makerspaceId) });
    },
  });
}

const PUBLICATION_KEYS = ["handle", "public_visible", "public_consented_at", "show_activity_graph", "show_events", "show_speaking",
  "show_projects", "show_machine_activity", "show_bookings", "show_loans"] as const;
// Only publication fields: a dirty profile form keeps its unsaved text, which the panel reseeds from the cache.
function pickPublication(data: MemberProfile) {
  return Object.fromEntries(PUBLICATION_KEYS.filter(key => key in data).map(key => [key, data[key]])) as Partial<MemberProfile>;
}

export function useTimeline(makerspaceId: number) {
  return useQuery({
    queryKey: timelineKey(makerspaceId),
    // At most 100 entries in pages of 24, so every page is read and the editor shows them all.
    queryFn: async () => {
      const rows: TimelineEntry[] = [];
      for (let page = 1; page <= 5; page += 1) {
        const body = await memberRequest<{ next?: string | null; results?: TimelineEntry[] }>(`${root(makerspaceId)}/timeline?page=${page}`);
        rows.push(...(Array.isArray(body?.results) ? body.results : []));
        if (!body?.next) break;
      }
      return rows;
    },
    retry: false,
  });
}

export function useTimelineMutations(makerspaceId: number) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: timelineKey(makerspaceId) });
  const save = useMutation({
    mutationFn: ({ id, draft }: { id?: number; draft: TimelineDraft }) => memberRequest<TimelineEntry>(
      id ? `${root(makerspaceId)}/timeline/${id}` : `${root(makerspaceId)}/timeline`,
      { method: id ? "PATCH" : "POST", body: JSON.stringify(draft) }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => memberRequest<void>(`${root(makerspaceId)}/timeline/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  return { save, remove };
}
