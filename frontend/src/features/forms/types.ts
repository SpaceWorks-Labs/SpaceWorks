export const QUESTION_TYPES = ["short_text", "long_text", "number", "date", "date_of_birth", "single_choice", "multi_choice", "yes_no", "email", "phone", "url", "asset_reference", "age_at_event", "emergency_contact"] as const;
export type QuestionType = typeof QUESTION_TYPES[number];
export type Condition = { all: Condition[] } | { any: Condition[] } | {
  field_id: string; op: "eq" | "ne" | "in" | "contains" | "is_set"; value?: unknown;
};
export interface Question {
  id: string; type: QuestionType; label: string; required?: boolean; help?: string; placeholder?: string;
  profile_field_key?: string; show_if?: Condition;
  visibility?: "member" | "server";
  options?: { id: string; label: string; other?: boolean }[];
  bounds?: { min?: number; max?: number; min_length?: number; max_length?: number; min_selections?: number; max_selections?: number; other_max_length?: number };
  disclosure?: { organizer: boolean; reviewer: boolean; judge: boolean };
}
export interface FormSchemaV2 {
  schema_version: 2; form_id: string; revision: number; questions: Question[];
  event_context?: { event_id: number; event_date_revision: number; timezone_name: string; as_of_date: string };
}
export type Answers = Record<string, unknown>;
export type FieldErrors = Record<string, string | string[] | Record<string, string | string[]>>;
export type Derivation = { source: { kind: "inline_dob"; date_of_birth: string } | { kind: "saved_detail"; field_key: "date_of_birth"; version: number }; reviewed_event_date_revision: number; reviewed_as_of_date: string };
export interface FormState {
  answers: Answers; derivations: Record<string, Derivation>; save_choices: Record<string, boolean>;
  saved_detail_versions: Record<string, number>;
}
export const SENSITIVE_KEYS = new Set(["resume", "date_of_birth", "dietary_needs", "accessibility_needs", "emergency_contact"]);
export const PROFILE_KEYS = ["name", "phone", "institution", "organization", "study_level", "country", "skills", "github_url", "linkedin_url", "portfolio_url", "resume", "shirt_size", "dietary_needs", "accessibility_needs", "emergency_contact", "date_of_birth", "age_at_event"] as const;
