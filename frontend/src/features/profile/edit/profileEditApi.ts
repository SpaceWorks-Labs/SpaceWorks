import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberRequest, StructuredApiError } from "../../../lib/api";
import type { AccountProfile, ProfilePatch, TimelineRow } from "../accountProfileTypes";

export type TimelineEntry = TimelineRow;
export type TimelineDraft = Omit<TimelineEntry, "id">;

/** Every account-level profile route lives under /member/profile (the per-space ones are deprecated aliases). */
const ROOT = "/member/profile";
export const ownProfileKey = ["member", "profile", "own"] as const;
export const timelineKey = ["member", "profile", "timeline"] as const;

/** The server's field message (handle grammar, reserved name, cooldown, https-only) beats a generic one. */
export function fieldError(error: unknown, field: string) {
  if (error instanceof StructuredApiError) {
    const value = error.body[field];
    const message = Array.isArray(value) ? value.filter(item => typeof item === "string").join(" ") : typeof value === "string" ? value : "";
    return message || error.message;
  }
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}

/** GET creates the row and claims the default handle on first call. */
export function useOwnProfile() {
  return useQuery({ queryKey: ownProfileKey, queryFn: () => memberRequest<AccountProfile>(ROOT), retry: false });
}

/** PATCH with any subset. The 200 body is the saved owner payload, written straight into the cache. */
export function usePatchProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfilePatch) => memberRequest<AccountProfile>(ROOT, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: data => { client.setQueryData(ownProfileKey, data); return client.invalidateQueries({ queryKey: ownProfileKey }); },
  });
}

export function useClaimHandle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (handle: string) => memberRequest<{ handle: string; claimed_at: string; changed_at: string }>(
      `${ROOT}/handle`, { method: "POST", body: JSON.stringify({ handle }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ownProfileKey }),
  });
}

/** Also turns the open web off and clears the consent stamp (server side). */
export function useReleaseHandle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => memberRequest<void>(`${ROOT}/handle`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ownProfileKey }),
  });
}

export function useTimeline() {
  return useQuery({
    queryKey: timelineKey,
    // At most 100 entries in pages of 24, so every page is read and the editor shows them all.
    queryFn: async () => {
      const rows: TimelineEntry[] = [];
      for (let page = 1; page <= 5; page += 1) {
        const body = await memberRequest<{ next?: string | null; results?: TimelineEntry[] }>(`${ROOT}/timeline?page=${page}`);
        rows.push(...(Array.isArray(body?.results) ? body.results : []));
        if (!body?.next) break;
      }
      return rows;
    },
    retry: false,
  });
}

export function useTimelineMutations() {
  const client = useQueryClient();
  const refresh = () => Promise.all([client.invalidateQueries({ queryKey: timelineKey }), client.invalidateQueries({ queryKey: ownProfileKey })]);
  const save = useMutation({
    mutationFn: ({ id, draft }: { id?: number; draft: TimelineDraft }) => memberRequest<TimelineEntry>(
      id ? `${ROOT}/timeline/${id}` : `${ROOT}/timeline`, { method: id ? "PATCH" : "POST", body: JSON.stringify(draft) }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => memberRequest<void>(`${ROOT}/timeline/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  return { save, remove };
}
