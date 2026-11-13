import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberRequest, StructuredApiError } from "../../lib/api";

/** Decision 223 (d): supervised workshop sessions (`machines.supervised_sessions`). The
 *  instructor may be a member, so every route is on the member prefix and is called with the
 *  person session even from the staff console (as the signatory and mentor screens do). */
export type SupervisedParticipant = { user: number; name: string; added_at: string; removed_at: string | null };
export type SupervisedUse = { id: number; user: number; instructor: number; started_at: string; ended_at: string | null; note: string };
export type SupervisedSession = {
  id: number; makerspace: number; machine: number; machine_name: string; instructor: number; instructor_name: string;
  event: number | null; note: string; opened_at: string; closed_at: string | null; is_open: boolean;
  participants: SupervisedParticipant[]; uses: SupervisedUse[];
};
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
/** `member/supervised-sessions/{id}/people`: people checked in or registered for the session's event (0.12.0). */
export type SupervisedPerson = { id: number; display_name: string };
/** `member/makerspaces/{id}/machines`: the public machine projection plus `id`, for active members (0.12.0). */
export type MemberMachine = {
  id: number; name: string; machine_type: { name: string; icon: string }; image_url: string | null;
  status: "idle" | "running" | "reserved" | "maintenance" | "offline"; usage_hours: string;
};
export type SessionFilter = "open" | "closed";

export const supervisedKeys = {
  all: ["supervised-sessions"] as const,
  list: (msId: number, status: SessionFilter, page: number, machineId?: number) =>
    ["supervised-sessions", "list", msId, status, page, machineId ?? null] as const,
  detail: (id: number) => ["supervised-sessions", "detail", id] as const,
  people: (id: number, q: string) => ["supervised-sessions", "people", id, q] as const,
  machines: (msId: number, page: number) => ["member-machines", msId, page] as const,
};

const CODES: Record<string, string> = {
  supervised_session_closed: t`This supervised session has closed.`,
  machine_unavailable: t`This machine is down or under maintenance, so it can't be supervised now.`,
  machine_in_use: t`Someone is using this machine, or a supervised session is already open on it.`,
  machine_locked_out: t`Overdue safety maintenance blocks this machine until it is done.`,
  not_supervised: t`Add this person to the session before recording their use.`,
  use_already_open: t`This person already has a use in progress.`,
  use_closed: t`This use has already ended.`,
  member_account_required: t`Supervised sessions need a personal account.`,
  feature_disabled: t`Supervised sessions are switched off for this space.`,
  module_disabled: t`Machines are switched off for this space.`,
  instructor_must_be_adult: t`Supervised sessions must be led by an adult instructor.`,
};

/** Friendly copy for the service's refusals (machines/supervised.py); its own sentence otherwise. */
export function supervisedErrorMessage(error: unknown): string {
  if (error instanceof StructuredApiError) {
    const known = error.code ? CODES[error.code] : undefined;
    if (known) return known;
    if (error.status === 403 && /certified instructor/i.test(error.message)) return t`Only an instructor certified on this machine can open a supervised session.`;
    if (error.status === 404) return t`That session, machine or account could not be found.`;
    if (error.status === 403 && !error.detail) return t`You don't lead this session.`;
  }
  return error instanceof Error && error.message ? error.message : t`Something went wrong. Try again.`;
}

const post = <T,>(path: string, body: unknown = {}) => memberRequest<T>(path, { method: "POST", body: JSON.stringify(body) });

/** `machineId` narrows server-side (`?machine=`), so every page holds only that machine's sessions. */
export function useSupervisedSessions(msId: number, status: SessionFilter, page: number, machineId?: number, enabled = true) {
  const machine = machineId ? `&machine=${machineId}` : "";
  return useQuery({ queryKey: supervisedKeys.list(msId, status, page, machineId), enabled: enabled && msId > 0, retry: false,
    queryFn: () => memberRequest<Page<SupervisedSession>>(`/member/makerspaces/${msId}/supervised-sessions?status=${status}&page=${page}${machine}`) });
}

/** The instructor's supervisee search: two characters minimum; 404 for anyone but the open session's instructor. */
export function useSupervisedPeople(sessionId: number, q: string) {
  return useQuery({ queryKey: supervisedKeys.people(sessionId, q), enabled: q.length >= 2, retry: false,
    queryFn: ({ signal }) => memberRequest<{ results: SupervisedPerson[] }>(
      `/member/supervised-sessions/${sessionId}/people?${new URLSearchParams({ q })}`, { signal }) });
}

/** The member's machines with ids (24 a page): the machine choice for "Start a supervised session". */
export function useMemberMachines(msId: number, page: number, enabled = true) {
  return useQuery({ queryKey: supervisedKeys.machines(msId, page), enabled: enabled && msId > 0, retry: false,
    queryFn: ({ signal }) => memberRequest<Page<MemberMachine>>(`/member/makerspaces/${msId}/machines?page=${page}`, { signal }) });
}

export function useSupervisedSession(id: number) {
  return useQuery({ queryKey: supervisedKeys.detail(id), retry: false,
    queryFn: () => memberRequest<SupervisedSession>(`/member/supervised-sessions/${id}`) });
}

export function useOpenSupervisedSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ machineId, ...body }: { machineId: number; note?: string; event_id?: number }) =>
      post<SupervisedSession>(`/member/machines/${machineId}/supervised-sessions`, body),
    onSuccess: session => { client.setQueryData(supervisedKeys.detail(session.id), session); return client.invalidateQueries({ queryKey: supervisedKeys.all }); },
  });
}

/** Every step on one session: each answers the session or a use, then the session and lists refresh. */
export function useSupervisedSteps(id: number) {
  const client = useQueryClient();
  const settle = (session?: SupervisedSession) => {
    if (session) client.setQueryData(supervisedKeys.detail(id), session);
    return client.invalidateQueries({ queryKey: supervisedKeys.all });
  };
  const base = `/member/supervised-sessions/${id}`;
  return {
    add: useMutation({ mutationFn: (userId: number) => post<SupervisedSession>(`${base}/supervisees`, { user_id: userId }), onSuccess: settle }),
    remove: useMutation({ mutationFn: (userId: number) => memberRequest<SupervisedSession>(`${base}/supervisees/${userId}`, { method: "DELETE" }), onSuccess: settle }),
    start: useMutation({ mutationFn: (userId: number) => post<SupervisedUse>(`${base}/uses`, { user_id: userId }), onSuccess: () => settle() }),
    end: useMutation({ mutationFn: (useId: number) => post<SupervisedUse>(`/member/supervised-uses/${useId}/end`), onSuccess: () => settle() }),
    close: useMutation({ mutationFn: () => post<SupervisedSession>(`${base}/close`), onSuccess: settle }),
  };
}
