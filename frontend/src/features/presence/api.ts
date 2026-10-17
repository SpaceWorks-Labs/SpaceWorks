import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, staffRequest, tenantPublicRequest } from "../../lib/api";

// Hand-typed from the presence lane's contract (docs/p2-presence.md). The integrator
// regenerates `generated/api.ts` after the merge; these shapes then become aliases.
export type PresenceStatus = "working" | "visiting" | "attending_event" | "guest";
export type PresenceSession = {
  started_at: string; expires_at: string; ended_at: string | null; end_reason: string; active: boolean;
  status: PresenceStatus; project_id: number | null; hide_on_display: boolean;
  names_displayed: boolean; personal_opt_out_allowed: boolean;
};
/** `personal_opt_out_allowed` / `names_displayed` at the top level are a requested contract
 * addition (so the sheet knows the rule before the first check-in); read them when present. */
export type PresenceCurrent = { active: boolean; session: PresenceSession | null; renewable?: PresenceSession | null; presets?: number[];
  personal_opt_out_allowed?: boolean; names_displayed?: boolean };
export type PresenceProject = { id: number; title: string; public_visible: boolean };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type PresenceStartInput = { duration_minutes: number; status?: "working" | "visiting" | "guest";
  project_id?: number | null; hide_on_display?: boolean; latitude?: number; longitude?: number; accuracy?: number };
export type PresenceRosterRow = PresenceSession & { account_id: number; display_name: string; role_label: string };
export type PresencePrivacy = { show_names: boolean; allow_personal_opt_out: boolean };
/** The public TV row: exactly these fields, never identifiers or contacts. */
export type PresenceTVRow = { display_name: string; status: PresenceStatus; since: string;
  project_title?: string; event_title?: string };

export const DEFAULT_PRESETS = [60, 120, 180, 240];

export const presenceKeys = {
  member: (slug: string) => ["member", slug, "presence"] as const,
  projects: (slug: string) => ["member", slug, "presence", "projects"] as const,
  preference: (slug: string) => ["member", slug, "presence", "preference"] as const,
  roster: (makerspaceId: number, page: number) => ["presence", "staff", makerspaceId, "roster", page] as const,
  privacy: (makerspaceId: number) => ["presence", "staff", makerspaceId, "privacy"] as const,
  tv: (slug: string) => ["presence", "tv", slug] as const,
};

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const base = (slug: string) => `/public/${encodeURIComponent(slug)}/presence-sessions`;

export const presenceApi = {
  current: (slug: string) => memberRequest<PresenceCurrent>(`${base(slug)}/current`),
  start: (slug: string, input: PresenceStartInput) => memberRequest<PresenceSession>(base(slug), json(input)),
  renew: (slug: string, minutes: number) => memberRequest<PresenceSession>(`${base(slug)}/current/renew`, json({ duration_minutes: minutes })),
  end: (slug: string) => memberRequest<PresenceCurrent>(`${base(slug)}/current/end`, { method: "POST" }),
  projects: (slug: string) => memberRequest<Page<PresenceProject>>(`${base(slug)}/projects`),
  preference: (slug: string) => memberRequest<{ hide_on_display: boolean }>(`${base(slug)}/preferences`),
  roster: (makerspaceId: number, page: number) =>
    staffRequest<Page<PresenceRosterRow>>(`/admin/makerspace/${makerspaceId}/presence-sessions/current?page=${page}`),
  staffCheckIn: (makerspaceId: number, input: PresenceStartInput & { account_id: number }) =>
    staffRequest<PresenceSession>(`/admin/makerspace/${makerspaceId}/presence-sessions/check-in`, json(input)),
  staffCheckOut: (makerspaceId: number, accountId: number) =>
    staffRequest<PresenceCurrent>(`/admin/makerspace/${makerspaceId}/presence-sessions/check-out`, json({ account_id: accountId })),
  privacy: (makerspaceId: number) => staffRequest<PresencePrivacy>(`/admin/makerspace/${makerspaceId}/presence-sessions/privacy`),
  savePrivacy: (makerspaceId: number, next: Partial<PresencePrivacy>) =>
    staffRequest<PresencePrivacy>(`/admin/makerspace/${makerspaceId}/presence-sessions/privacy`, { method: "PATCH", body: JSON.stringify(next) }),
  tv: (slug: string) => tenantPublicRequest<PresenceTVRow[]>(slug, `/public/makerspaces/${encodeURIComponent(slug)}/presence/now/`),
};

/** The member's own session. `enabled` carries the module gate: off means no request at all. */
export function usePresenceCurrent(slug: string, enabled: boolean) {
  return useQuery({ queryKey: presenceKeys.member(slug), queryFn: () => presenceApi.current(slug),
    enabled: enabled && Boolean(slug), retry: false, refetchInterval: 60_000 });
}

export function usePresenceMutations(slug: string) {
  const client = useQueryClient();
  const settle = (data: PresenceCurrent) => client.setQueryData(presenceKeys.member(slug), (old: PresenceCurrent | undefined) => ({ ...old, ...data }));
  const onSession = (session: PresenceSession) => settle({ active: session.active, session, renewable: null });
  return {
    start: useMutation({ mutationFn: (input: PresenceStartInput) => presenceApi.start(slug, input), onSuccess: onSession }),
    renew: useMutation({ mutationFn: (minutes: number) => presenceApi.renew(slug, minutes), onSuccess: onSession }),
    end: useMutation({ mutationFn: () => presenceApi.end(slug), onSuccess: () => settle({ active: false, session: null, renewable: null }) }),
  };
}
