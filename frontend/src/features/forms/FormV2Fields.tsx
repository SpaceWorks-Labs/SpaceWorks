import type { ReactNode } from "react";
import { visibleQuestions } from "./conditions";
import { QuestionInput } from "./QuestionInput";
import { ageAtEvent } from "./ageAtEvent";
import { SENSITIVE_KEYS, type FieldErrors, type FormSchemaV2, type FormState, type Question } from "./types";

function errorText(error: FieldErrors[string] | undefined): string {
  if (!error) return "";
  if (typeof error === "string") return error;
  if (Array.isArray(error)) return error.join(" ");
  return Object.entries(error).map(([key, message]) => `${key}: ${Array.isArray(message) ? message.join(" ") : message}`).join(" ");
}
export function FormV2Fields({ schema, value, onChange, errors = {}, renderAsset, allowSavedDetails = true }: {
  allowSavedDetails?: boolean;
  schema: FormSchemaV2; value: FormState; onChange: (state: FormState) => void; errors?: FieldErrors;
  renderAsset?: (question: Question, selected: unknown, onChange: (value: unknown) => void) => ReactNode;
}) {
  return <div className="grid gap-6">{visibleQuestions(schema, value.answers).map(q => {
    const saveKey = allowSavedDetails ? q.type === "age_at_event" ? "date_of_birth" : q.profile_field_key : undefined;
    const source = value.derivations[q.id]?.source;
    const error = errorText(errors[q.id]);
    const changeAnswer = (answer: unknown) => {
      const choices = { ...value.save_choices };
      const versions = { ...value.saved_detail_versions };
      if (saveKey && choices[saveKey] === undefined) { choices[saveKey] = !SENSITIVE_KEYS.has(saveKey); versions[saveKey] ??= 0; }
      onChange({ ...value, answers: { ...value.answers, [q.id]: answer }, save_choices: choices, saved_detail_versions: versions });
    };
    const descriptionId = `question-${q.id}-description`;
    return <fieldset key={q.id} className="grid min-w-0 gap-2 rounded-2xl border border-line bg-panel p-4">
      <legend className="px-1 text-sm font-semibold text-ink">{q.label}{q.required ? " (required)" : ""}</legend>
      <div id={descriptionId} className="grid gap-1 text-sm text-muted">{q.help ? <p>{q.help}</p> : null}
        <p>Shared with: {[q.disclosure?.organizer !== false && "organizers", q.disclosure?.reviewer && "reviewers", q.disclosure?.judge && "judges"].filter(Boolean).join(", ") || "event processing only"}.</p></div>
      {q.type === "age_at_event" ? <div className="grid gap-2">
        <p className="text-sm text-muted">Age is calculated at the event start{schema.event_context ? ` (${schema.event_context.as_of_date})` : ""}. Your birth date is private unless this form separately asks for it.</p>
        {source?.kind === "saved_detail" ? <p className="text-sm">Using your saved birth date.</p> : <label className="grid gap-1 text-sm">Date of birth<input className="desk-input" type="date" required={q.required} value={source?.kind === "inline_dob" ? source.date_of_birth : ""} onChange={e => {
          if (!schema.event_context) return;
          onChange({ ...value, derivations: { ...value.derivations, [q.id]: { source: { kind: "inline_dob", date_of_birth: e.target.value }, reviewed_event_date_revision: -1, reviewed_as_of_date: "" } }, save_choices: { ...value.save_choices, date_of_birth: value.save_choices.date_of_birth ?? false }, saved_detail_versions: { ...value.saved_detail_versions, date_of_birth: value.saved_detail_versions.date_of_birth ?? 0 } });
        }} /></label>}
        {source?.kind === "inline_dob" && schema.event_context ? <p className="text-sm">Age at event start: {ageAtEvent(source.date_of_birth, schema.event_context.as_of_date) ?? "Enter a valid date"}</p> : null}
        {value.derivations[q.id] && schema.event_context ? <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" required={q.required} checked={value.derivations[q.id].reviewed_event_date_revision === schema.event_context.event_date_revision && value.derivations[q.id].reviewed_as_of_date === schema.event_context.as_of_date} onChange={e => onChange({ ...value, derivations: { ...value.derivations, [q.id]: { ...value.derivations[q.id], reviewed_event_date_revision: e.target.checked ? schema.event_context!.event_date_revision : -1, reviewed_as_of_date: e.target.checked ? schema.event_context!.as_of_date : "" } } })} />I reviewed the event start date used for my age</label> : null}
      </div> : q.type === "asset_reference" && renderAsset ? renderAsset(q, value.answers[q.id], changeAnswer) : <QuestionInput question={q} value={value.answers[q.id]} onChange={changeAnswer} invalid={Boolean(error)} describedBy={`${descriptionId}${error ? ` question-${q.id}-error` : ""}`} />}
      {error ? <p id={`question-${q.id}-error`} role="alert" className="text-sm text-danger">{error}</p> : null}
      {saveKey ? <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={value.save_choices[saveKey] ?? !SENSITIVE_KEYS.has(saveKey)} onChange={e => onChange({ ...value, save_choices: { ...value.save_choices, [saveKey]: e.target.checked }, saved_detail_versions: { ...value.saved_detail_versions, [saveKey]: value.saved_detail_versions[saveKey] ?? 0 } })} />Save {q.type === "age_at_event" ? "date of birth" : q.label.toLowerCase()} to my Saved details</label> : null}
    </fieldset>;
  })}</div>;
}
