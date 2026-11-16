// Decision 223 (k), lane L3b: minors and guardian consent, volunteer credit, the join funnel.
// Hand-typed, like the neighbouring feature api modules.
import { memberRequest, staffRequest } from "../../lib/api";

export type CommunityPolicy = {
  minors_admitted: boolean; minors_minimum_age: number; adult_age: number; guardian_must_be_present: boolean;
  minors_may_borrow: boolean; minors_may_use_machines: boolean; consent_valid_days: number;
  volunteer_minutes_per_credit: number; volunteer_credit_kind: "discount" | "free_days"; volunteer_credit_amount: string;
  volunteer_credit_days: number; join_followup_enabled: boolean; join_followup_delay_hours: number;
};
export type MinorProfile = {
  id: number; user_id: number; user_name: string; age: number | null; declared_under_age: boolean;
  guardian_user_id: number | null; guardian_name: string; guardian_email: string; guardian_phone: string;
  consent_state: "valid" | "none"; consent_valid_until: string | null; consent_terms_version: string | null;
  /** The live consent (0.12.0): the one staff may revoke from the list. */
  current_consent_id: number | null; current_consent_version: string | null; current_consent_signed_at: string | null;
  cleared_at: string | null; created_at: string;
};
export type MinorInput = {
  user_email?: string; user_id?: number; date_of_birth?: string; declared_under_age?: boolean;
  guardian_name?: string; guardian_email?: string; guardian_phone?: string;
};
export type GuardianTerms = { id: number; version: string; body: string; is_active: boolean; created_at: string; superseded_at: string | null };
export type Consent = { id: number; terms_version: string; method: string; signed_at: string; valid_until: string; revoked_at: string | null };
/** One row of a minor's consent history (staff view, 0.12.0): live, expired or revoked. */
export type ConsentHistoryRow = Consent & { signer: string; recorded_by_name: string; revoked_by_name: string; is_live: boolean };
export type Dependent = { profile_id: number; dependent_name: string; consent_state: "valid" | "none"; consent_valid_until: string | null; consents: Consent[] };
export type GuardianPage = { terms: GuardianTerms | null; dependents: Dependent[] };
export type VolunteerEntry = {
  id: number; member: number; member_name: string; minutes: number; worked_on: string; description: string;
  source: string; status: string; reviewed_at: string | null; review_note: string; created_at: string;
};
export type VolunteerCredit = {
  id: number; member: number; member_name: string; kind: "discount" | "free_days"; amount: string; days: number; currency: string; status: string;
  minutes_converted: number; applied_payment: number | null; applied_amount: string | null; applied_at: string | null; created_at: string;
};
export type JoinPrefill = { name: string; email: string; phone: string; source: "event" | "guest_pass"; source_ref: number; source_label: string };
type Paged<T> = { count: number; next: string | null; previous: string | null; results: T[] };

const json = (method: string, body?: unknown): RequestInit => ({ method, body: JSON.stringify(body ?? {}) });
const admin = (id: number) => `/admin/makerspaces/${id}`;
const member = (id: number) => `/member/makerspaces/${id}`;

export const communityKeys = {
  all: (id: number) => ["community", id] as const,
  policy: (id: number) => ["community", id, "policy"] as const,
  minors: (id: number, page: number) => ["community", id, "minors", page] as const,
  consents: (id: number, profileId: number) => ["community", id, "minor-consents", profileId] as const,
  terms: (id: number) => ["community", id, "guardian-terms"] as const,
  hours: (id: number, status: string, page: number) => ["community", id, "volunteer-hours", status, page] as const,
  credits: (id: number, page: number) => ["community", id, "volunteer-credits", page] as const,
  guardian: (id: number) => ["member", "community", id, "guardian"] as const,
  ownConsent: (id: number) => ["member", "community", id, "own-consent"] as const,
  myHours: (id: number) => ["member", "community", id, "volunteer-hours"] as const,
  myCredits: (id: number) => ["member", "community", id, "volunteer-credits"] as const,
};

export const communityStaffApi = {
  policy: (id: number) => staffRequest<CommunityPolicy>(`${admin(id)}/community-policy`),
  savePolicy: (id: number, next: Partial<CommunityPolicy>) => staffRequest<CommunityPolicy>(`${admin(id)}/community-policy`, json("PATCH", next)),
  minors: (id: number, page: number) => staffRequest<Paged<MinorProfile>>(`${admin(id)}/minors?page=${page}`),
  recordMinor: (id: number, input: MinorInput) => staffRequest<MinorProfile>(`${admin(id)}/minors`, json("POST", input)),
  clearMinor: (id: number, profileId: number) => staffRequest<MinorProfile>(`${admin(id)}/minors/${profileId}/clear`, json("POST")),
  consents: (id: number, profileId: number) => staffRequest<ConsentHistoryRow[]>(`${admin(id)}/minors/${profileId}/consents`),
  recordConsent: (id: number, profileId: number, input: { signed_name: string; accepted: boolean; operation_id?: string }) =>
    staffRequest<Consent>(`${admin(id)}/minors/${profileId}/consents`, json("POST", input)),
  revokeConsent: (id: number, consentId: number) => staffRequest<Consent>(`${admin(id)}/guardian-consents/${consentId}/revoke`, json("POST")),
  terms: (id: number) => staffRequest<GuardianTerms[]>(`${admin(id)}/guardian-terms`),
  publishTerms: (id: number, input: { version: string; body: string }) => staffRequest<GuardianTerms>(`${admin(id)}/guardian-terms`, json("POST", input)),
  hours: (id: number, status: string, page: number) =>
    staffRequest<Paged<VolunteerEntry>>(`${admin(id)}/volunteer-hours?${new URLSearchParams({ status, page: String(page) })}`),
  logHours: (id: number, input: { member_id: number; minutes: number; worked_on: string; description: string }) =>
    staffRequest<VolunteerEntry>(`${admin(id)}/volunteer-hours`, json("POST", input)),
  decide: (id: number, entryId: number, approve: boolean, note = "") =>
    staffRequest<VolunteerEntry>(`${admin(id)}/volunteer-hours/${entryId}/decide`, json("POST", { approve, note })),
  importShifts: (id: number) => staffRequest<{ created: number }>(`${admin(id)}/volunteer-hours/import-event-shifts`, json("POST")),
  credits: (id: number, page: number) => staffRequest<Paged<VolunteerCredit>>(`${admin(id)}/volunteer-credits?page=${page}`),
  voidCredit: (id: number, creditId: number, reason = "") => staffRequest<VolunteerCredit>(`${admin(id)}/volunteer-credits/${creditId}/void`, json("POST", { reason })),
};

/** Open item A27: the caller's own guardian-consent standing (minors only; never guardian contact details). */
export type OwnConsentStatus = {
  applies: boolean; state: "not_applicable" | "current" | "pending" | "expired" | "terms_missing"; valid_until: string | null;
  guardian_named: boolean; guardian_must_be_present: boolean; may_borrow: boolean; may_use_machines: boolean;
};

export const communityMemberApi = {
  ownConsent: (id: number) => memberRequest<OwnConsentStatus>(`${member(id)}/my-guardian-consent`),
  guardian: (id: number) => memberRequest<GuardianPage>(`${member(id)}/guardian-consents`),
  sign: (id: number, profileId: number, input: { signed_name: string; accepted: true; operation_id: string }) =>
    memberRequest<Consent>(`${member(id)}/guardian-consents/${profileId}/sign`, json("POST", input)),
  revoke: (id: number, profileId: number) => memberRequest<Consent[]>(`${member(id)}/guardian-consents/${profileId}/revoke`, json("POST")),
  hours: (id: number) => memberRequest<VolunteerEntry[]>(`${member(id)}/volunteer-hours`),
  logHours: (id: number, input: { minutes: number; worked_on: string; description: string }) =>
    memberRequest<VolunteerEntry>(`${member(id)}/volunteer-hours`, json("POST", input)),
  credits: (id: number) => memberRequest<VolunteerCredit[]>(`${member(id)}/volunteer-credits`),
  joinPrefill: (id: number, source: { registration_id?: number; guest_pass_id?: number }) =>
    memberRequest<JoinPrefill>(`${member(id)}/join-prefill?${new URLSearchParams(Object.entries(source).map(([key, value]) => [key, String(value)]))}`),
};
