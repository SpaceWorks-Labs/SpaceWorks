import type { ApiPath } from "../../generated/api";
import type { CustomFormSchema } from "../forms/customFormTypes";
import type { PaymentSummary } from "./PaymentReconcileActions";

export type EventStatus = "draft" | "published" | "cancelled" | "completed";
export type EventRegistrationStatus =
  | "pending_approval"
  | "registered"
  | "waitlisted"
  | "rejected"
  | "cancelled"
  | "attended";
export type EventRegistrationCounts = Record<EventRegistrationStatus, number>;

export type EventAccent = "" | "maker_teal" | "workshop_orange" | "citron" | "sky_blue" | "warm_yellow";

export type StaffEvent = {
  accent_preset?: EventAccent;
  staff_permissions?: import("./eventStaffPermissions").EventPermission[];
  can_manage_staff?: boolean;
  can_duplicate?: boolean;
  ticketing_features?: string[];
  broadcasts_enabled?: boolean;
  badge_sensitive_fields_allowed?: boolean;
  report_features?: string[];
  participating_organizations?: { id: number; name: string }[];
  audience_label?: string | null;
  organization_admission_blocked?: boolean;
  id: number;
  makerspace_id: number;
  registration_audience?: "members" | "accounts" | "invite" | "participating_organizations";
  category_id?: number | null; tags?: string[];
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  timezone_name: string;
  location: string;
  /** Parity E-B7: an outside venue's street address and an https map link (the link wins for directions). */
  venue_address?: string;
  venue_map_url?: string;
  capacity: number;
  payment_amount: string;
  /** Lowercase ISO code the space charges in; `payment_amount` is in this currency. */
  currency?: string;
  /** The caller's own track/window limit as a limited co-organizer (decision 221(i)); prefills the staff
   *  invite form. Single-event reads (detail GET/PATCH) only: null when unlimited and on list reads. */
  my_limit?: { track_ids: number[]; valid_from: string | null; valid_until: string | null } | null;
  registration_requires_approval: boolean;
  registration_cutoff_at: string | null;
  registration_cutoff_lead_minutes: number | null;
  cancellation_cutoff_hours?: number | null;
  effective_registration_cutoff_at: string | null;
  registration_open: boolean;
  offline_checkin_enabled: boolean;
  is_public: boolean;
  /** L1: who can find it and whether the public page is up. */
  listing?: "listed" | "unlisted";
  page_state?: "live" | "offline";
  delivery_mode?: "in_person" | "online" | "hybrid";
  /** Plaintext only for readers with edit_details while online events are on. */
  join_url?: string | null;
  join_url_set?: boolean;
  show_registration_count?: boolean;
  image_url: string | null;
  status: EventStatus;
  custom_form: CustomFormSchema | null;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
  registration_counts: EventRegistrationCounts;
  organizers: { id: number; slug: string; name: string }[];
  /** Selected audience organizations: registration eligibility only, never authority. */
  audience_organizations?: { id: number; slug: string; name: string }[];
  series_summary: {
    id: number; public_token: string; title: string; timezone: string;
  } | null;
  series_revision: number | null;
  series_override_fields: string[];
};

export type EventRegistration = {
  no_longer_eligible?: boolean;
  id: number;
  event_id: number;
  name: string;
  email: string;
  phone: string;
  status: EventRegistrationStatus;
  payment: PaymentSummary | null;
  custom_answers?: import("../forms/customFormTypes").CustomAnswerSnapshot;
  cancelled_at?: string | null;
  status_before_cancel?: EventRegistrationStatus | null;
  restore_until?: string | null;
  /** Parity E-B5: the end of a paid place's pay window, while one is open. */
  pay_by?: string | null;
  created_at: string;
  /** The ticket bought, when ticket types are on (EB5 ticket column). */
  ticket_type_id?: number | null;
  ticket_type_name?: string | null;
};

export type EventPayload = {
  accent_preset?: EventAccent;
  registration_audience?: "members" | "accounts" | "invite" | "participating_organizations";
  category_id?: number | null; tags?: string[];
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  timezone_name: string;
  location: string;
  venue_address?: string;
  venue_map_url?: string;
  capacity: number;
  payment_amount: string;
  registration_requires_approval: boolean;
  registration_cutoff_at: string | null;
  registration_cutoff_lead_minutes: number | null;
  cancellation_cutoff_hours?: number | null;
  is_public: boolean;
  show_registration_count?: boolean;
  custom_form: CustomFormSchema;
  // L1: who can find it, the public page state and online delivery (join link write-only).
  listing?: "listed" | "unlisted";
  page_state?: "live" | "offline";
  delivery_mode?: "in_person" | "online" | "hybrid";
  join_url?: string;
};

/** Create-only extras, applied in the same transaction as the new draft. */
export type EventCreatePayload = EventPayload & {
  organization_ids?: number[];
  audience_organization_ids?: number[];
  collaborator_slugs?: string[];
};

export type EventPatch = Partial<EventPayload> & { inherit_fields?: string[] };
export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const EVENT_LIST_PATH: ApiPath = "/api/v1/admin/makerspaces/{makerspace_id}/events/";
export const EVENT_DETAIL_PATH: ApiPath = "/api/v1/admin/events/{id}/";
export const EVENT_ORGANIZERS_PATH = "/api/v1/admin/events/{id}/organizers/";
export const EVENT_PUBLISH_PATH: ApiPath = "/api/v1/admin/events/{id}/publish/";
export const EVENT_CANCEL_PATH: ApiPath = "/api/v1/admin/events/{id}/cancel/";
export const EVENT_COMPLETE_PATH: ApiPath = "/api/v1/admin/events/{id}/complete/";
export const EVENT_REGISTRATIONS_PATH: ApiPath = "/api/v1/admin/events/{id}/registrations/";
export const MARK_ATTENDED_PATH: ApiPath = "/api/v1/admin/event-registrations/{id}/mark-attended/";
export const CHECK_IN_RESOLVE_PATH: ApiPath = "/api/v1/admin/events/{id}/check-in/resolve/";
export const ELIGIBLE_MEMBERS_PATH: ApiPath = "/api/v1/admin/events/{id}/eligible-members/";

export function staffPath(path: string, replacements: Record<string, number>) {
  return Object.entries(replacements).reduce(
    (value, [key, replacement]) => value.replace(`{${key}}`, String(replacement)),
    path.replace("/api/v1", ""),
  );
}

export const eventKeys = {
  all: (makerspaceId: number) => ["events", makerspaceId] as const,
  list: (makerspaceId: number) => ["events", makerspaceId, "list"] as const,
  detail: (eventId: number) => ["event", eventId] as const,
  registrations: (eventId: number) => ["event", eventId, "registrations"] as const,
  badgeTemplate: (eventId: number) => ["event", eventId, "badge-template"] as const,
  checkinStation: (eventId: number) => ["event", eventId, "check-in", "station"] as const,
  checkinHistory: (eventId: number) => ["event", eventId, "check-in", "history"] as const,
};

export function eligibleMemberKey(eventId: number) {
  return ["event", eventId, "eligible-members"] as const;
}
