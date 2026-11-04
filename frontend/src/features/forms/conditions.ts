import { SENSITIVE_KEYS, type Answers, type Condition, type FormSchemaV2, type FormState, type Question } from "./types";

const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
function comparable(value: unknown): unknown {
  const object = record(value);
  return object?.option_id ?? object?.option_ids ?? value;
}
function answered(value: unknown): boolean {
  const actual = comparable(value);
  return actual !== undefined && actual !== null && actual !== "" && (!Array.isArray(actual) || actual.length > 0);
}
function normalizeEarlier(question: Question, value: unknown): unknown {
  const bounds = question.bounds ?? {};
  if (["short_text", "long_text", "email", "phone", "url"].includes(question.type)) {
    if (typeof value !== "string") return undefined;
    const clean = value.normalize("NFC").trim();
    const maximum = ({ short_text: 500, long_text: 5000, email: 254, phone: 32, url: 2048 } as Record<string, number>)[question.type];
    if (!clean || clean.length < (bounds.min_length ?? 0) || clean.length > Math.min(maximum, bounds.max_length ?? maximum)) return undefined;
    if (question.type === "phone") {
      const phone = clean.replace(/[\s().-]/g, "").replace(/^00/, "+");
      return /^\+[1-9][0-9]{6,14}$/.test(phone) ? phone : undefined;
    }
    return clean;
  }
  if (question.type === "number") {
    if (typeof value !== "number" && (typeof value !== "string" || !/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value))) return undefined;
    const number = Number(value);
    return Number.isFinite(number) && (bounds.min === undefined || number >= bounds.min) && (bounds.max === undefined || number <= bounds.max) ? number : undefined;
  }
  if (question.type === "yes_no") return typeof value === "boolean" ? value : undefined;
  if (question.type === "single_choice" || question.type === "multi_choice") {
    const object = record(value);
    if (!object) return undefined;
    const selected = question.type === "single_choice" ? [object.option_id] : object.option_ids;
    if (!Array.isArray(selected) || !selected.length || selected.some(key => !question.options?.some(option => option.id === key))) return undefined;
    return question.type === "single_choice" ? object : { ...object, option_ids: question.options?.filter(option => selected.includes(option.id)).map(option => option.id) };
  }
  return value;
}
export function conditionMatches(condition: Condition, answers: Answers, depth = 1): boolean {
  if (depth > 3) return false;
  if ("all" in condition) return condition.all.length > 0 && condition.all.every(item => conditionMatches(item, answers, depth + 1));
  if ("any" in condition) return condition.any.some(item => conditionMatches(item, answers, depth + 1));
  const actual = comparable(answers[condition.field_id]);
  if (condition.op === "is_set") return answered(actual) === (condition.value !== false);
  if (!Object.prototype.hasOwnProperty.call(answers, condition.field_id) || !answered(actual)) return false;
  switch (condition.op) {
    case "eq": return actual === condition.value;
    case "ne": return actual !== condition.value;
    case "in": return Array.isArray(condition.value) && condition.value.includes(actual);
    case "contains": return Array.isArray(actual) ? actual.includes(condition.value) : typeof actual === "string" && typeof condition.value === "string" && actual.includes(condition.value);
  }
}
export function visibleQuestions(schema: FormSchemaV2, answers: Answers) {
  const visibleAnswers: Answers = {};
  return schema.questions.filter(question => {
    const visible = question.visibility !== "server" && (!question.show_if || conditionMatches(question.show_if, visibleAnswers));
    if (visible) { const normalized = normalizeEarlier(question, answers[question.id]); if (answered(normalized)) visibleAnswers[question.id] = normalized; }
    return visible;
  });
}
/** Keep hidden answers only in component memory; never send them to admission or the vault. */
export function memberFormInput(schema: FormSchemaV2, state: FormState) {
  const visible = visibleQuestions(schema, state.answers);
  const keys = new Set(visible.filter(q => q.type === "age_at_event" ? state.derivations[q.id] : answered(state.answers[q.id])).map(q => q.type === "age_at_event" ? "date_of_birth" : q.profile_field_key).filter((key): key is string => Boolean(key)));
  const sensitive = new Set(schema.questions.filter(q => q.sensitive).map(q => q.profile_field_key));
  const choices = Object.fromEntries([...keys].map(key => [key, state.save_choices[key] ?? (!sensitive.has(key) && !SENSITIVE_KEYS.has(key))]));
  return {
    form: { schema_version: 2 as const, form_id: schema.form_id, revision: schema.revision },
    answers: Object.fromEntries(visible.filter(q => q.type !== "age_at_event" && state.answers[q.id] !== undefined).map(q => [q.id, state.answers[q.id]])),
    derivations: Object.fromEntries(visible.filter(q => q.type === "age_at_event" && state.derivations[q.id]).map(q => [q.id, state.derivations[q.id]])),
    save_choices: choices,
    saved_detail_versions: Object.fromEntries([...keys].filter(key => choices[key] || state.saved_detail_versions[key] !== undefined).map(key => [key, state.saved_detail_versions[key] ?? 0])),
    event_date_revision: schema.event_context?.event_date_revision,
  };
}
