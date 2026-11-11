import type { FormSchemaV2, FormSection, Question } from "./types";

// Parity O-B2: section headings in a v2 form. A heading carries no answer, so it lives beside the
// questions (`schema.sections`), anchored to the question it sits above; the server mirrors these
// rules in `forms_schema/schema_items_static.py`.

export const MAX_SECTIONS = 20;
export const PRINTABLE_TYPES = new Set(["short_text", "long_text", "number", "date", "single_choice", "multi_choice", "yes_no"]);

export type FormItem = { kind: "section"; section: FormSection } | { kind: "question"; question: Question };

/**
 * Questions and headings in render order. `visible` is the already-filtered question list
 * (conditions applied): a heading shows only when a visible question follows it before the next
 * heading, so a block whose every question is hidden never leaves an orphan title behind.
 */
export function formItems(schema: FormSchemaV2, visible: Question[]): FormItem[] {
  const anchored = new Map<string, FormSection[]>();
  for (const section of schema.sections ?? []) anchored.set(section.before, [...anchored.get(section.before) ?? [], section]);
  const shown = new Set(visible.map(question => question.id));
  const items: FormItem[] = [];
  let pending: FormSection | null = null;
  for (const question of schema.questions) {
    const headings = anchored.get(question.id) ?? [];
    // Two headings above one question: only the last one introduces it.
    if (headings.length) pending = headings[headings.length - 1];
    if (!shown.has(question.id)) continue;
    if (pending) { items.push({ kind: "section", section: pending }); pending = null; }
    items.push({ kind: "question", question });
  }
  return items;
}

export function newSection(before: string, heading: string): FormSection {
  return { id: `s-${crypto.randomUUID()}`, before, heading };
}

/** The first question with no heading of its own yet (else the first question) for a new heading. */
export function nextSectionAnchor(schema: FormSchemaV2): string | null {
  const taken = new Set((schema.sections ?? []).map(section => section.before));
  return schema.questions.find(question => !taken.has(question.id))?.id ?? schema.questions[0]?.id ?? null;
}

/** A schema without `questionId`: its headings move to the next question (or the previous one at the end). */
export function withoutQuestion(schema: FormSchemaV2, questionId: string): FormSchemaV2 {
  const index = schema.questions.findIndex(question => question.id === questionId);
  const questions = schema.questions.filter(question => question.id !== questionId);
  const heir = questions[index]?.id ?? questions[index - 1]?.id;
  const sections = (schema.sections ?? []).flatMap(section => section.before !== questionId ? [section]
    : heir ? [{ ...section, before: heir }] : []);
  return { ...schema, questions, ...(schema.sections ? { sections } : {}) };
}

/** `printable` is only kept where the server accepts it (plain, non-sensitive types). */
export function printableAllowed(question: Question) {
  return PRINTABLE_TYPES.has(question.type) && !question.sensitive;
}
