export type FieldKey = "name" | "phone" | "institution" | "organization" | "study_level" | "country" | "skills" | "github_url" | "linkedin_url" | "portfolio_url" | "resume" | "shirt_size" | "dietary_needs" | "accessibility_needs" | "emergency_contact" | "date_of_birth";
export type SavedValue = string | string[] | { name: string; relationship: string; phone: string } | { asset_id: number; sha256: string };
export type SavedField = { field_key: FieldKey; value: SavedValue | null; version: number; sensitive: boolean; default_save: boolean };
export type SavedDetails = { version: number; fields: SavedField[]; readiness: "ready" | "unavailable" };
export type SavedCommand = { operation_id: string; expected_version: number };
export type ResumeAsset = { asset_id: number; state: "uploading" | "validating" | "ready" | "failed" | "deleting" | "deleted"; sha256: string; bytes: number; version: number; generation: number; code?: string;
  upload?: { method: "POST"; url: string; fields: Record<string, string>; expires_at: string } };
export type ExportJob = { job_id: string; state: "queued" | "building" | "ready" | "failed" | "expired"; expires_at?: string };
type EventContext = { event_id: number; makerspace_id: number };
export type StagePrefillContext = EventContext & { subject_kind: "stage_response"; posting_id?: never } & (
  { subject_id: number; stage_form_id?: number; creation_operation_id?: never } |
  { subject_id?: never; stage_form_id: number; creation_operation_id: string }
);
export type PrefillSelector = { context: (EventContext & { subject_kind: "registration" | "application" | "role_assignment"; subject_id?: number; posting_id?: number; stage_form_id?: never; creation_operation_id?: never }) | StagePrefillContext;
  form_id: string; form_revision: number; event_date_revision: number };
export type Prefill = { form_revision: number; event_date_revision: number; values: Record<string, SavedValue>; saved_detail_versions: Partial<Record<FieldKey, number>>; save_defaults: Partial<Record<FieldKey, boolean>>;
  derivation_inputs: Record<string, { source: { kind: "saved_detail"; field_key: "date_of_birth"; version: number }; value: number; as_of_date: string }> };
export type SaveIntentFields = Partial<Record<FieldKey, { state: "applied" | "unchanged" | "conflict" | "failed"; version?: number; current_version?: number; code?: string }>>;
export type SaveIntent = { operation_id: string; state: "pending" | "applied" | "conflict" | "failed"; fields: SaveIntentFields; retryable: boolean; code?: string };
export type FormSlot = "base" | `stage:${number}`;
export type FormSaveIntent = { slot: FormSlot; operation_id: string; fields: SaveIntentFields } & (
  { intent_id: null; state: "not_requested"; status_url: null } |
  { intent_id: string; state: SaveIntent["state"]; status_url: string }
);
export const savedDetailsKey = (actorId: number) => ["member", "saved-details", window.location.host, actorId] as const;
