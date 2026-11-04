import type { FormSchemaV2, FormState } from "../../forms/types";
import type { Prefill } from "../../accountSavedDetails/types";
import { memberFormInput } from "../../forms/conditions";

export function stagePayload(schema: FormSchemaV2, value: FormState, dateRevision: number) {
  return { ...memberFormInput(schema, value), derivations: {}, event_date_revision: dateRevision };
}
export function applyStageSuggestions(schema: FormSchemaV2, value: FormState, prefill: Prefill): FormState {
  const answers = { ...value.answers };
  const versions = { ...value.saved_detail_versions };
  const choices = { ...value.save_choices };
  for (const question of schema.questions) {
    const key = question.profile_field_key;
    if (!key || ["date_of_birth", "age_at_event"].includes(key) || answers[question.id] !== undefined) continue;
    const saved = prefill.values[key];
    if (saved === undefined) continue;
    answers[question.id] = question.type === "single_choice" ? { option_id: saved } : question.type === "multi_choice" ? { option_ids: saved } : saved;
    versions[key] = prefill.saved_detail_versions[key as keyof typeof prefill.saved_detail_versions] ?? 0;
    // Sensitive values always need a fresh affirmative choice in this form.
    choices[key] = question.sensitive || ["resume", "dietary_needs", "accessibility_needs", "emergency_contact"].includes(key)
      ? false : prefill.save_defaults[key as keyof typeof prefill.save_defaults] ?? false;
  }
  return { answers, derivations: {}, saved_detail_versions: versions, save_choices: choices };
}
export function utcInstant(value: string) {
  const instant = new Date(value);
  if (!value || !Number.isFinite(instant.getTime())) throw new Error("Enter a valid date and time.");
  return instant.toISOString().replace(/\.000Z$/, "Z");
}
export function localDateTime(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
