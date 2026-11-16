import type { CustomFormSchema } from "./customFormTypes";
import type { FormSchemaV2, QuestionType } from "./types";
/** Called only by the explicit editor upgrade action, never implicitly on read. */
export function upgradeLegacyForm(schema: CustomFormSchema, formId: string): FormSchemaV2 {
  return { schema_version: 2, form_id: formId, revision: 1, questions: (schema ?? []).map(q => ({
    id: q.id, label: q.label, type: (q.type === "paragraph" ? "long_text" : q.type === "dropdown" ? "single_choice" : q.type) as QuestionType,
    required: q.required, ...(q.options.length ? { options: q.options.map((label, i) => ({ id: `option-${i + 1}`, label })) } : {}),
    disclosure: { organizer: true, reviewer: false, judge: false },
  })) };
}
