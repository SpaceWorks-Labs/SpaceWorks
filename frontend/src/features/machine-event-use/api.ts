import { memberRequest, staffRequest } from "../../lib/api";

/** Decision 342: machine use logged with an event. Server values only; the cost decision moves no money. */
export type EventOption = { id: number; title: string; starts_at: string; ends_at: string | null };
export type MachineEventLink = { event: EventOption | null; source: string; locked: boolean; options: EventOption[] };
export type UseKind = "session" | "request" | "booking";

export type MachineUseRow = {
  link_id: number; kind: UseKind; subject_id: number; title: string; machine_type: string; person: string; minutes: number;
  consumables: { label: string; unit: string; quantity: string }[]; source: string; created_at: string;
  charge: { amount: string; currency: string; status: string } | null; cost_decision: "approved" | "withdrawn" | null;
};
export type MachineUse = {
  rows: MachineUseRow[]; can_decide_costs: boolean;
  totals: { sessions: number; bookings?: number; requests: number; minutes: number; consumables: { label: string; unit: string; quantity: string }[];
    charged: Record<string, string>; approved_to_event: Record<string, string> };
};

export const eventUseKeys = {
  mine: (makerspaceId: number) => ["member", "machine-use-events", makerspaceId] as const,
  link: (makerspaceId: number, kind: UseKind, id: number) => ["machine-use-event", makerspaceId, kind, id] as const,
  staffOptions: (makerspaceId: number) => ["machine-use-event-options", makerspaceId] as const,
  event: (makerspaceId: number, eventId: number) => ["event-machine-use", makerspaceId, eventId] as const,
};

export const fetchMyEvents = (makerspaceId: number) =>
  memberRequest<EventOption[]>(`/member/makerspaces/${makerspaceId}/machine-use/events/`);

const linkUrl = (makerspaceId: number, kind: UseKind, id: number) => `/admin/makerspace/${makerspaceId}/machine-use/${kind}/${id}/event`;
export const fetchStaffEventOptions = (makerspaceId: number) =>
  staffRequest<EventOption[]>(`/admin/makerspace/${makerspaceId}/machine-use/events`);
export const fetchLink = (makerspaceId: number, kind: UseKind, id: number) => staffRequest<MachineEventLink>(linkUrl(makerspaceId, kind, id));
export const saveLink = (makerspaceId: number, kind: UseKind, id: number, eventId: number | null) =>
  staffRequest<MachineEventLink>(linkUrl(makerspaceId, kind, id), { method: "PUT", body: JSON.stringify({ event_id: eventId }) });

export const fetchEventUse = (makerspaceId: number, eventId: number) =>
  staffRequest<MachineUse>(`/admin/makerspace/${makerspaceId}/events/${eventId}/machine-use`);
export const decideCost = (makerspaceId: number, eventId: number, linkId: number, decision: "approved" | "withdrawn") =>
  staffRequest<void>(`/admin/makerspace/${makerspaceId}/events/${eventId}/machine-use/${linkId}/cost`,
    { method: "POST", body: JSON.stringify({ decision }) });
