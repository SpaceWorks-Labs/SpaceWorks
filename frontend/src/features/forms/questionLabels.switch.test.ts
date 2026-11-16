import { describe, expect, it } from "vitest";
import { questionTypeLabel, filePurposeLabel, questionBoundLabel } from "./questionLabels";

describe("questionTypeLabel", () => {
  it.each([
    ["short_text", "Short text"],
    ["long_text", "Long text"],
    ["number", "Number"],
    ["date", "Date"],
    ["date_of_birth", "Date of birth"],
    ["single_choice", "Single choice"],
    ["multi_choice", "Multiple choice"],
    ["yes_no", "Yes / No"],
    ["email", "Email"],
    ["phone", "Phone"],
    ["url", "Web address"],
    ["asset_reference", "Equipment reference"],
    ["age_at_event", "Age at the event"],
    ["emergency_contact", "Emergency contact"],
    ["money", "Amount of money"],
    ["file", "File upload"],
    ["itinerary", "Travel itinerary"],
  ])("%s reads %s", (code, text) => expect(questionTypeLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(questionTypeLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("filePurposeLabel", () => {
  it.each([
    ["stage_form_file", "stage form file"],
    ["reimbursement_receipt", "expense receipt"],
    ["reimbursement_payee_document", "payee document"],
  ])("%s reads %s", (code, text) => expect(filePurposeLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(filePurposeLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("questionBoundLabel", () => {
  it.each([
    ["max_length", "Maximum length"],
    ["min_length", "Minimum length"],
    ["min", "Minimum"],
    ["max", "Maximum"],
    ["min_selections", "Minimum selections"],
    ["max_selections", "Maximum selections"],
    ["other_max_length", "Maximum length of \"Other\""],
  ])("%s reads %s", (code, text) => expect(questionBoundLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(questionBoundLabel("zz_unknown_code")).toBe("zz unknown code"));
});

