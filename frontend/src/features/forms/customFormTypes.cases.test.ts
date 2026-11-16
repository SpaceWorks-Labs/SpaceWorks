import { describe, expect, it } from "vitest";
import { customAnswerErrors, CHOICE_QUESTION_TYPES, QUESTION_TYPE_LABELS, validateCustomAnswers, type CustomFormQuestion } from "./customFormTypes";
import type { FormSchemaV2 } from "./types";

const q = (over: Partial<CustomFormQuestion>): CustomFormQuestion => ({ id: "a", label: "A", type: "short_text", options: [], required: false, ...over });
const v2 = (questions: unknown[]): FormSchemaV2 => ({ schema_version: 2, form_id: "f", revision: 1, questions } as unknown as FormSchemaV2);

describe("question type tables", () => {
  it("names every type", () => expect(QUESTION_TYPE_LABELS).toEqual({ short_text: "Short text", paragraph: "Paragraph", number: "Number", date: "Date",
    single_choice: "Single choice", multi_choice: "Multiple choice", dropdown: "Dropdown", yes_no: "Yes / No" }));
  it("marks exactly the three choice types", () => expect([...CHOICE_QUESTION_TYPES].sort()).toEqual(["dropdown", "multi_choice", "single_choice"]));
});

describe("customAnswerErrors", () => {
  it.each([[null], [undefined], ["text"], [5], [[]], [["a"]]])("returns nothing for %j", (value) => expect(customAnswerErrors(value)).toEqual({}));
  it("joins the string messages of a field and ignores non-strings", () => expect(customAnswerErrors({ a: ["One.", "Two."], b: "Solo", c: [1, null], d: 7 })).toEqual({ a: "One. Two.", b: "Solo" }));
  it("flattens a nested object into 'field: message' text", () => expect(customAnswerErrors({ group: { x: ["Bad"], y: { z: "Deep" } } })).toEqual({ group: "x: Bad y: z: Deep" }));
  it("drops a nested object that carries no message", () => expect(customAnswerErrors({ group: { x: [] }, ok: "Yes" })).toEqual({ ok: "Yes" }));
});

describe("validateCustomAnswers (v1 list schema)", () => {
  it("accepts no schema", () => expect(validateCustomAnswers(null, { x: "" })).toEqual({}));
  it("requires a required question, treating '', undefined and [] as empty", () => {
    const schema = [q({ id: "a", required: true }), q({ id: "b", required: true, type: "multi_choice" }), q({ id: "c", required: true })];
    expect(validateCustomAnswers(schema, { a: "", b: [] })).toEqual({ a: "This question is required.", b: "This question is required.", c: "This question is required." });
  });
  it("does not require an optional blank question", () => expect(validateCustomAnswers([q({ id: "a" })], {})).toEqual({}));
  it("accepts zero and false as answers", () => expect(validateCustomAnswers([q({ id: "n", type: "number", required: true }), q({ id: "y", type: "yes_no", required: true })], { n: 0, y: false })).toEqual({}));
  it("rejects a non-numeric number but allows a numeric string", () => {
    const schema = [q({ id: "n", type: "number" })];
    expect(validateCustomAnswers(schema, { n: "abc" })).toEqual({ n: "Enter a valid number." });
    expect(validateCustomAnswers(schema, { n: "12.5" })).toEqual({});
  });
  it("reports 'required' rather than 'valid number' for an empty required number", () => expect(validateCustomAnswers([q({ id: "n", type: "number", required: true })], { n: "" })).toEqual({ n: "This question is required." }));
});

describe("validateCustomAnswers (v2 schema)", () => {
  const schema = v2([
    { id: "name", type: "short_text", required: true },
    { id: "age", type: "number", required: false },
    { id: "dob", type: "age_at_event", required: true },
    { id: "hidden", type: "short_text", required: true, show_if: { question_id: "name", operator: "equals", value: "never" } },
  ]);
  it("requires visible required questions, treating null as empty", () => expect(validateCustomAnswers(schema, { name: null })).toEqual({ name: "This question is required." }));
  it("never asks the browser to validate derived age answers", () => expect(validateCustomAnswers(schema, { name: "Ann" })).toEqual({}));
  it("does not demand a question hidden by its condition", () => expect(validateCustomAnswers(schema, { name: "Ann" })).not.toHaveProperty("hidden"));
  it("rejects a non-numeric number answer, and skips a blank optional one", () => {
    expect(validateCustomAnswers(schema, { name: "Ann", age: "x" })).toEqual({ age: "Enter a valid number." });
    expect(validateCustomAnswers(schema, { name: "Ann", age: "" })).toEqual({});
  });
  it("treats an empty array as empty for a required question", () => expect(validateCustomAnswers(v2([{ id: "m", type: "multi_choice", required: true }]), { m: [] })).toEqual({ m: "This question is required." }));
});
