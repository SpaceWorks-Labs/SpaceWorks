import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import fixture from "../../../../backend/tests/events/programme/contracts/fixtures/form-v2.json";
import emergency from "../../../../backend/tests/events/programme/contracts/fixtures/emergency-contact-v2.json";
import { FormV2Fields } from "./FormV2Fields";
import { conditionMatches, memberFormInput, visibleQuestions } from "./conditions";
import { ageAtEvent } from "./ageAtEvent";
import { CustomFormFields } from "./CustomFormFields";
import { CustomFormBuilder } from "./CustomFormBuilder";
import { CustomAnswersView } from "./CustomAnswersView";
import type { CustomAnswerSnapshotV2 } from "./customFormTypes";
import type { FormSchemaV2, FormState } from "./types";
import { expectNoA11yViolations } from "../../test/axe";
const schema = fixture.schema as FormSchemaV2;
const empty: FormState = { answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {} };
describe("F canonical form consumer", () => {
  it("keeps v2 form controls accessible with conditional questions", async () => {
    const { container } = render(<FormV2Fields schema={schema} value={empty} onChange={() => {}} />);
    await expectNoA11yViolations(container);
  });
  it("drops hidden known answers, hidden save choices and numeric age from HTTP inputs", () => {
    const input = memberFormInput(schema, { ...fixture.member_input, answers: { ...fixture.member_input.answers, diet_note: "private hidden", age: 99 }, save_choices: { institution: true, dietary_needs: true, date_of_birth: false } } as FormState);
    expect(input.answers).toEqual(fixture.member_input.answers);
    expect(input.save_choices).toEqual({ institution: true, date_of_birth: false });
    expect(input.derivations).toEqual(fixture.member_input.derivations);
    expect(input.saved_detail_versions).not.toHaveProperty("dietary_needs");
  });
  it("uses stable Other option IDs when selecting conditions", () => {
    const answers = { diet: { option_id: "other", text: "Vegetarian" } };
    expect(visibleQuestions(schema, answers).map(q => q.id)).toContain("diet_note");
    expect(conditionMatches({ field_id: "diet", op: "eq", value: "Vegetarian" }, answers)).toBe(false);
  });
  it("never lets hidden answers satisfy ne conditions", () => {
    const nested: FormSchemaV2 = { ...schema, questions: [{ id: "a", type: "short_text", label: "A" }, { id: "b", type: "short_text", label: "B", show_if: { field_id: "a", op: "eq", value: "yes" } }, { id: "c", type: "short_text", label: "C", show_if: { field_id: "b", op: "ne", value: "no" } }, { id: "server", type: "short_text", label: "Hidden metadata", visibility: "server" }] };
    expect(visibleQuestions(nested, { a: "no", b: "retained draft", server: "evil" }).map(q => q.id)).toEqual(["a"]);
  });
  it.each([["short_text", " yes ", "yes"], ["number", "2", 2], ["phone", "0091 (98765)-43210", "+919876543210"]])("normalizes earlier %s answers before visibility", (type, raw, canonical) => {
    const form = { ...schema, questions: [{ id: "first", type, label: "First" }, { id: "child", type: "short_text", label: "Child", show_if: { field_id: "first", op: "eq", value: canonical } }] } as FormSchemaV2;
    expect(visibleQuestions(form, { first: raw }).map(q => q.id)).toEqual(["first", "child"]);
  });
  it.each([false, 0])("treats %s as an answered value", value => expect(conditionMatches({ field_id: "a", op: "is_set" }, { a: value })).toBe(true));
  it("supports is_set false and bounded nested evaluation", () => {
    expect(conditionMatches({ field_id: "a", op: "is_set", value: false }, {})).toBe(true);
    expect(conditionMatches({ field_id: "a", op: "is_set" }, { a: { option_ids: [] } })).toBe(false);
    expect(conditionMatches({ all: [{ any: [{ all: [{ field_id: "a", op: "eq", value: 1 }] }] }] }, { a: 1 })).toBe(false);
  });
  it("renders compound emergency answers with opt-in saving and nested errors", () => {
    function Demo() { const [state, setState] = useState<FormState>({ ...empty, answers: emergency.raw }); return <FormV2Fields schema={emergency.schema as FormSchemaV2} value={state} onChange={setState} errors={{ emergency: { phone: ["Enter an international phone."] } }} />; }
    render(<Demo />);
    expect(screen.getByLabelText("Contact name")).toHaveValue(emergency.raw.emergency.name);
    expect(screen.getByLabelText("Contact phone")).toHaveValue(emergency.raw.emergency.phone);
    const save = screen.getByRole("checkbox", { name: /Save emergency contact/ });
    expect(save).not.toBeChecked(); fireEvent.click(save); expect(save).toBeChecked();
    expect(screen.getByRole("alert")).toHaveTextContent("phone: Enter an international phone.");
  });
  it("allows a blank relationship even for a required emergency contact", () => {
    const requiredSchema = { ...emergency.schema, questions: [{ ...emergency.question, required: true }] } as FormSchemaV2;
    render(<FormV2Fields schema={requiredSchema} value={{ ...empty, answers: { emergency: { ...emergency.raw.emergency, relationship: "" } } }} onChange={() => {}} />);
    expect(screen.getByLabelText("Contact name")).toBeRequired(); expect(screen.getByLabelText("Contact phone")).toBeRequired(); expect(screen.getByLabelText("Relationship")).not.toBeRequired(); expect(screen.getByLabelText("Relationship")).toBeValid();
  });
  it("defaults nonsensitive mapped answers on and sensitive fields off", () => {
    render(<FormV2Fields schema={schema} value={empty} onChange={() => {}} />);
    expect(screen.getByRole("checkbox", { name: /Save school or organisation/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Save date of birth/ })).not.toBeChecked();
    expect(screen.queryByText("Details (required)")).not.toBeInTheDocument();
  });
  it("requires explicit event-date review after birth date entry", () => {
    let latest = empty;
    function Demo() { const [state, setState] = useState<FormState>(empty); return <FormV2Fields schema={schema} value={state} onChange={next => { latest = next; setState(next); }} />; }
    render(<Demo />); fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "2004-05-12" } });
    const review = screen.getByRole("checkbox", { name: "I reviewed the event start date used for my age" }); expect(review).not.toBeChecked(); expect(latest.derivations.age.reviewed_event_date_revision).toBe(-1);
    expect(screen.getByText("Age at event start: 22")).toBeVisible(); fireEvent.click(review); expect(latest.derivations.age.reviewed_event_date_revision).toBe(7); expect(latest.derivations.age.reviewed_as_of_date).toBe("2026-12-01");
  });
  it("dispatches existing field and builder wrappers to v2 without converting v1", () => {
    const { unmount } = render(<CustomFormFields schema={emergency.schema as FormSchemaV2} answers={emergency.raw} onChange={() => {}} />);
    expect(screen.getByLabelText("Contact name")).toHaveValue("Fixture Contact"); unmount();
    render(<CustomFormBuilder value={schema} onChange={() => {}} />); expect(screen.getByRole("region", { name: "Form builder" })).toBeVisible();
  });
  it("keeps legacy primitive choice values unchanged", () => {
    const change = vi.fn(); render(<CustomFormFields schema={[{ id: "choice", label: "Choose one", type: "single_choice", options: ["First", "Second"], required: true }]} answers={{ choice: "First" }} onChange={change} />);
    expect(screen.getByRole("radio", { name: "First" })).toBeChecked(); fireEvent.click(screen.getByRole("radio", { name: "Second" })); expect(change).toHaveBeenCalledWith({ choice: "Second" });
  });
  it("renders canonical v2 snapshots without derivation IDs or DOB", () => {
    render(<CustomAnswersView snapshot={fixture.canonical_snapshot as CustomAnswerSnapshotV2} />);
    expect(screen.getByText("Maker College")).toBeVisible(); expect(screen.queryByText("19")).not.toBeInTheDocument(); expect(screen.queryByText("2004-05-12")).not.toBeInTheDocument();
  });
  it.each([["2004-02-29", "2026-02-28", 21], ["2004-02-29", "2026-03-01", 22], ["2000-12-31", "2026-01-01", 25], ["2004-02-30", "2026-12-01", null], ["2027-01-01", "2026-12-01", null]])("computes %s age at event local date %s only", (dob, date, age) => expect(ageAtEvent(String(dob), String(date))).toBe(age));
});
