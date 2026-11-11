import type { CustomAnswerSnapshot, CustomAnswers, CustomFormSchema } from "../forms/customFormTypes";
import { memberRequest, staffRequest, tenantPublicRequest } from "../../lib/api";

export type JoinMode = "open" | "approval" | "invite_only" | "vouch" | "closed";
export type PaymentTiming = "after_activation" | "before_activation";
export type AdmissionRecipe = "free_open" | "free_vouch" | "paid_approval" | "paid_invite_only" | "closed";
export type AdmissionSettings = {
  join_mode: JoinMode;
  vouches_required: number;
  voucher_min_tenure_days: number;
  voucher_pending_limit: number;
  vouch_expiry_days: number;
  vouch_replaces_approval: boolean;
  payment_timing: PaymentTiming;
  // At runtime this may also be a v2 form (`FormSchemaV2`); `CustomFormFields`/`CustomFormBuilder` route on its shape.
  application_schema: CustomFormSchema;
  default_plan: number | null;
  joining_fee: string;
  joining_fee_currency: string;
  rejoin_dues_rule: "never" | "once" | "each_join" | "after_lapse";
  request_expiry_days: number;
  // Release 2 (L4): lapse days, member-number pattern (X12), consent ledger (X10).
  rejoin_after_days?: number | null;
  member_number_pattern?: string;
  privacy_notice_version?: string;
  consent_purposes?: { key: string; label: string; description: string }[];
};
export type PublicAdmission = Pick<AdmissionSettings, "join_mode" | "vouches_required" | "payment_timing" | "application_schema" | "joining_fee"> & {
  default_plan: { id: number; name: string; amount: string; currency: string } | null;
  joining_fee_currency?: string;
  /** Parity O-B2: what the default plan's join form collects besides its questions. */
  join_fields?: JoinFieldModes;
};
/** Parity O-B2: a plan's join-form extras; every value is off/hidden while the space's switches are off. */
export type JoinFieldMode = "hidden" | "optional" | "required";
export type JoinFieldModes = { photo: "off" | "optional" | "required"; phone: JoinFieldMode; state: JoinFieldMode };
/** Sent as `join_fields` on a join request or a resubmission; a photo is uploaded first (see `joinPhotoPresign`). */
export type JoinFieldsInput = { phone?: string; state_code?: string; photo?: { object_key: string; content_type: string; consent: true } };
export type AdmissionPayment = { id: number; status: string; amount: string; currency: string };
export type AdmissionVouch = { voucher_id: number; voucher_name: string; created_at: string; expires_at: string };
export type AdmissionRequest = {
  id: number;
  state: string;
  application_answers?: CustomAnswerSnapshot | null;
  vouches?: AdmissionVouch[];
  admission_payment?: AdmissionPayment | null;
  expires_at?: string | null;
  // Parity O-B2: "ask for changes". The note is the reviewer's, shown to the applicant.
  changes_note?: string;
  changes_requested_at?: string | null;
  changes_rounds?: number;
  /** While `changes_requested`: the form this application was made with (staff-only questions removed). */
  edit_schema?: CustomFormSchema;
  /** While `changes_requested`: the plan's join-form extras. */
  join_fields?: JoinFieldModes | null;
};
export type PhotoPresign = { object_key: string; content_type: string; url: string; fields?: Record<string, string>; method?: string; headers?: Record<string, string> };

export const admissionKeys = {
  settings: (id: number) => ["membership-admission", id] as const,
  public: (slug: string) => ["member", slug, "admission-settings"] as const,
  own: (id: number) => ["member", id, "admission"] as const,
};
export const publicAdmission = (slug: string) => tenantPublicRequest<PublicAdmission>(slug, `/public/${slug}/membership-admission`);
export const admissionSettings = (id: number) => staffRequest<AdmissionSettings>(`/admin/makerspaces/${id}/membership-admission`);
export const saveAdmissionSettings = (id: number, input: Partial<AdmissionSettings> & { recipe?: AdmissionRecipe }) =>
  staffRequest<AdmissionSettings>(`/admin/makerspaces/${id}/membership-admission`, { method: "PATCH", body: JSON.stringify(input) });
export const ownAdmission = (id: number) => memberRequest<AdmissionRequest | null>(`/member/makerspaces/${id}/admission`);
export const cancelAdmission = (id: number, requestId: number) => memberRequest<AdmissionRequest>(`/member/makerspaces/${id}/admission/${requestId}/cancel`, { method: "POST" });
export const vouchForAdmission = (id: number, requestId: number) => memberRequest<Pick<AdmissionRequest, "id" | "state">>(`/member/makerspaces/${id}/admission/${requestId}/vouch`, { method: "POST" });
/** Parity O-B2: edit and resubmit an application that was sent back (once). Fields left out keep what is on file. */
export const resubmitAdmission = (requestId: number, input: { application_answers?: CustomAnswers; join_fields?: JoinFieldsInput }) =>
  memberRequest<AdmissionRequest>(`/memberships/requests/${requestId}`, { method: "PATCH", body: JSON.stringify(input) });
/** Parity O-B2: a staging-only upload URL for the join-form photo. */
export const joinPhotoPresign = (id: number, contentType: string, planId?: number | null) =>
  memberRequest<PhotoPresign>(`/member/makerspaces/${id}/admission/photo`, { method: "POST", body: JSON.stringify({ content_type: contentType, ...(planId ? { plan_id: planId } : {}) }) });
