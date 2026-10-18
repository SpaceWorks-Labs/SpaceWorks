import type { FormSchemaV2, QuestionType } from "./types";
import { visibleQuestions } from "./conditions";

export const CUSTOM_QUESTION_TYPES = [
  "short_text",
  "paragraph",
  "number",
  "date",
  "single_choice",
  "multi_choice",
  "dropdown",
  "yes_no",
] as const;

export type CustomQuestionType = (typeof CUSTOM_QUESTION_TYPES)[number];

export type CustomFormQuestion = {
  id: string;
  label: string;
  type: CustomQuestionType;
  options: string[];
  required: boolean;
};

export type CustomFormSchema = CustomFormQuestion[] | null;
export type VersionedCustomFormSchema = CustomFormSchema | FormSchemaV2;
export type CustomAnswerValue = string | number | boolean | string[];
export type CustomAnswers = Partial<Record<string, CustomAnswerValue>>;

export type StoredCustomAnswer = {
  id: string;
  label: string;
  type: CustomQuestionType;
  value: CustomAnswerValue;
};

export type CustomAnswerSnapshot = {
  version: 1;
  answers: StoredCustomAnswer[];
};
export type CustomAnswerSnapshotV2 = {
  version: 2; form_id: string; form_revision: number;
  answers: { id: string; label: string; type: QuestionType; value?: unknown; derivation_id?: number }[];
};

export const CHOICE_QUESTION_TYPES = new Set<CustomQuestionType>([
  "single_choice",
  "multi_choice",
  "dropdown",
]);

export const QUESTION_TYPE_LABELS: Record<CustomQuestionType, string> = {
  short_text: "Short text",
  paragraph: "Paragraph",
  number: "Number",
  date: "Date",
  single_choice: "Single choice",
  multi_choice: "Multiple choice",
  dropdown: "Dropdown",
  yes_no: "Yes / No",
};

export function customAnswerErrors(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, detail]) => {
      if (detail && typeof detail === "object" && !Array.isArray(detail)) {
        const nested = customAnswerErrors(detail);
        const text = Object.entries(nested).map(([field, message]) => `${field}: ${message}`).join(" ");
        return text ? [[key, text]] : [];
      }
      const messages = Array.isArray(detail) ? detail : [detail];
      const text = messages.filter((item): item is string => typeof item === "string").join(" ");
      return text ? [[key, text]] : [];
    }),
  );
}

export function validateCustomAnswers(schema: VersionedCustomFormSchema, answers: Record<string, unknown>) {
  const errors: Record<string, string> = {};
  if (schema && !Array.isArray(schema)) {
    for (const q of visibleQuestions(schema, answers)) {
      // Derived answers are validated by F/P's typed service, never as numeric browser values.
      if (q.type === "age_at_event") continue;
      const value = answers[q.id];
      const empty = value === undefined || value === null || value === "" || Array.isArray(value) && value.length === 0;
      if (q.required && empty) errors[q.id] = "This question is required.";
      if (q.type === "number" && !empty && !Number.isFinite(Number(value))) errors[q.id] = "Enter a valid number.";
    }
    return errors;
  }
  for (const question of schema ?? []) {
    const value = answers[question.id];
    const empty = value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
    if (question.required && empty) {
      errors[question.id] = "This question is required.";
    } else if (question.type === "number" && !empty && !Number.isFinite(Number(value))) {
      errors[question.id] = "Enter a valid number.";
    }
  }
  return errors;
}
