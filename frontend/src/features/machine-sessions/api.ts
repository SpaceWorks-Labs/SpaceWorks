import { t } from "@lingui/core/macro";
import { memberRequest, staffRequest, StructuredApiError } from "../../lib/api";

/** Lane L23 (#158): metered machine sessions. Server values only; no money is computed here. */
export type SessionRate = { unit_amount: string; currency: string; increment: number; minimum: number; discount_name: string };
export type SessionPayment = { id: number; amount: string; currency: string; status: string };
export type SessionStatus = "live" | "review" | "closed";
export type ChargeState = "job" | "none" | "running" | "raised" | "held" | "free";
export type SessionSource = "member_qr" | "staff" | "device";

export type MemberSession = {
  id: number; makerspace_id: number; machine_id: number; machine_name: string; machine_type_name: string;
  source: SessionSource; status: SessionStatus; started_at: string; ended_at: string | null; minutes: number;
  stop_reason: string; flagged: boolean; charge_state: ChargeState; rate: SessionRate | null; amount: string | null;
  payment: SessionPayment | null; event?: { id: number; title: string } | null;
};

export type SessionAmendment = { id: number; kind: "correct" | "assign" | "confirm"; minutes: number | null; member_id: number | null;
  reason: string; actor_name: string; created_at: string };

export type StaffSession = MemberSession & {
  member_id: number | null; member_name: string; needs_review: boolean; service_request_id: number | null;
  duration_minutes: number; amendments: SessionAmendment[];
};

export type SessionRefusal = { code: string; detail: string };
export type SessionPreview = {
  /** Optional: lets the start sheet show the type's training notes. */
  machine_type_id?: number; machine_id: number; machine_name: string; machine_type_name: string; machine_status: string; billing: boolean;
  rate: SessionRate | null; digest: string; max_minutes: number; closes_at: string | null; can_start: boolean;
  refusal: SessionRefusal | null; live_session: MemberSession | null;
};

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const sessionKeys = {
  preview: (machineId: number) => ["member", "machine-session-preview", machineId] as const,
  mine: (makerspaceId?: number) => ["member", "machine-sessions", makerspaceId ?? "all"] as const,
  allMine: ["member", "machine-sessions"] as const,
  staff: (makerspaceId: number, filters: string) => ["machine-sessions", makerspaceId, filters] as const,
  staffAll: (makerspaceId: number) => ["machine-sessions", makerspaceId] as const,
  settings: (makerspaceId: number, typeId: number) => ["machine-session-settings", makerspaceId, typeId] as const,
};

const json = (body?: unknown) => body === undefined ? undefined : JSON.stringify(body);

export const fetchSessionPreview = (machineId: number) => memberRequest<SessionPreview>(`/member/machines/${machineId}/session`);
export const startSession = (machineId: number, digest: string, eventId?: number) =>
  memberRequest<MemberSession>(`/member/machines/${machineId}/sessions/start`,
    { method: "POST", body: json({ digest, ...(eventId ? { event_id: eventId } : {}) }) });
export const stopSession = (id: number) => memberRequest<MemberSession>(`/member/machine-sessions/${id}/stop`, { method: "POST" });
export const fetchMySessions = (makerspaceId?: number) =>
  memberRequest<MemberSession[]>(`/member/machine-sessions${makerspaceId != null ? `?makerspace=${makerspaceId}` : ""}`);

export const fetchStaffSessions = (makerspaceId: number, filters: string) =>
  staffRequest<Page<StaffSession>>(`/admin/makerspaces/${makerspaceId}/machine-sessions${filters ? `?${filters}` : ""}`);
export const staffStartSession = (makerspaceId: number, machineId: number, memberId: number) =>
  staffRequest<StaffSession>(`/admin/makerspaces/${makerspaceId}/machine-sessions`,
    { method: "POST", body: json({ machine_id: machineId, member_id: memberId }) });
export const staffSessionAction = (id: number, action: "stop" | "confirm" | "amend" | "assign", body?: unknown) =>
  staffRequest<StaffSession>(`/admin/machine-sessions/${id}/${action}`, { method: "POST", body: json(body) });
export const fetchSessionSettings = (makerspaceId: number, typeId: number) =>
  staffRequest<{ session_max_minutes: number }>(`/admin/makerspaces/${makerspaceId}/machine-types/${typeId}/session-settings`);
export const saveSessionSettings = (makerspaceId: number, typeId: number, minutes: number) =>
  staffRequest<{ session_max_minutes: number }>(`/admin/makerspaces/${makerspaceId}/machine-types/${typeId}/session-settings`,
    { method: "PUT", body: json({ session_max_minutes: minutes }) });

const REFUSALS = (): Record<string, string> => ({
  member_restricted: t`Your account is restricted, so you can't use machines right now. Talk to staff.`,
  membership_required: t`Only active members of this space can use its machines.`,
  waiver_acceptance_required: t`Accept the space's current waiver in your member area first.`,
  presence_required: t`Check in at the space first, then scan the machine again.`,
  no_machine_access: t`A space manager has not given you access to this machine yet. Ask them to.`,
  machine_access_expired: t`Your access to this machine has ended. Ask a space manager to renew it.`,
  machine_unavailable: t`This machine is down or under maintenance.`,
  machine_locked_out: t`Overdue safety maintenance blocks this machine for now.`,
  machine_booked: t`Someone else has booked this machine for now.`,
  booking_required: t`Book this machine before using it.`,
  machine_in_use: t`Someone is using this machine right now.`,
  session_already_live: t`You already have a session running on this machine.`,
  session_closed: t`This session has already stopped.`,
  session_final: t`This session is already final; its charge follows the usual payment path.`,
  session_live: t`Stop the session first.`,
  session_unattributed: t`Assign this session to a member first.`,
  session_attributed: t`This session already belongs to a member.`,
  price_changed: t`The price changed since you opened this page. Check the new rate and start again.`,
});

export function refusalText(refusal: SessionRefusal | null | undefined) {
  if (!refusal) return "";
  return REFUSALS()[refusal.code] ?? refusal.detail;
}

export function sessionErrorMessage(error: unknown) {
  if (error instanceof StructuredApiError && error.code && REFUSALS()[error.code]) return REFUSALS()[error.code];
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}
