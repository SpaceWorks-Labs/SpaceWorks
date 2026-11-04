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
  payment: SessionPayment | null;
};

export type SessionAmendment = { id: number; kind: "correct" | "assign" | "confirm"; minutes: number | null; member_id: number | null;
  reason: string; actor_name: string; created_at: string };

export type StaffSession = MemberSession & {
  member_id: number | null; member_name: string; needs_review: boolean; service_request_id: number | null;
  duration_minutes: number; amendments: SessionAmendment[];
};

export type SessionRefusal = { code: string; detail: string; certifications?: string[] };
export type SessionPreview = {
  machine_id: number; machine_name: string; machine_type_name: string; machine_status: string; billing: boolean;
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
export const startSession = (machineId: number, digest: string) =>
  memberRequest<MemberSession>(`/member/machines/${machineId}/sessions/start`, { method: "POST", body: json({ digest }) });
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

const REFUSALS: Record<string, string> = {
  member_restricted: "Your account is restricted, so you can't use machines right now. Talk to staff.",
  membership_required: "Only active members of this space can use its machines.",
  waiver_acceptance_required: "Accept the space's current waiver in your member area first.",
  presence_required: "Check in at the space first, then scan the machine again.",
  certification_required: "You need the certification for this machine first.",
  machine_unavailable: "This machine is down or under maintenance.",
  machine_locked_out: "Overdue safety maintenance blocks this machine for now.",
  machine_booked: "Someone else has booked this machine for now.",
  booking_required: "Book this machine before using it.",
  machine_in_use: "Someone is using this machine right now.",
  session_already_live: "You already have a session running on this machine.",
  session_closed: "This session has already stopped.",
  session_final: "This session is already final; its charge follows the usual payment path.",
  session_live: "Stop the session first.",
  session_unattributed: "Assign this session to a member first.",
  session_attributed: "This session already belongs to a member.",
  price_changed: "The price changed since you opened this page. Check the new rate and start again.",
};

export function refusalText(refusal: SessionRefusal | null | undefined) {
  if (!refusal) return "";
  const base = REFUSALS[refusal.code] ?? refusal.detail;
  return refusal.certifications?.length ? `${base} (${refusal.certifications.join(", ")})` : base;
}

export function sessionErrorMessage(error: unknown) {
  if (error instanceof StructuredApiError && error.code && REFUSALS[error.code]) return REFUSALS[error.code];
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}
