import { describe, expect, it } from "vitest";
import contract from "../../../../../backend/tests/events/programme/contracts/reimbursement_addon.json";
import { applyStageSuggestions, stagePayload, utcInstant } from "./formPayload";
import type { Prefill } from "../../accountSavedDetails/types";
import type { FormSchemaV2, FormState } from "../../forms/types";

describe("frozen stage and Saved-details envelopes", () => {
  it("matches both inline question-map vectors and never sends stage derivations", () => {
    contract.submission.ordinary.payload.stage_forms.forEach((form, index) => {
      const { stage_form_id: _id, ...expected } = form;
      const value = { answers: form.answers, derivations: contract.form_envelope.base_derivation, save_choices: form.save_choices, saved_detail_versions: form.saved_detail_versions } as unknown as FormState;
      expect(stagePayload(contract.stages.inline_schemas[index] as FormSchemaV2, value, 1)).toEqual(expected);
    });
  });
  it("prefills only empty mapped values and requires fresh sensitive consent", () => {
    const schema: FormSchemaV2 = { schema_version: 2, form_id: "stage", revision: 1, questions: [
      { id: "school", type: "short_text", label: "School", profile_field_key: "institution" },
      { id: "access", type: "long_text", label: "Access", profile_field_key: "accessibility_needs", sensitive: true },
      { id: "dob", type: "date_of_birth", label: "DOB", profile_field_key: "date_of_birth" },
    ] };
    const value: FormState = { answers: { school: "My edit" }, derivations: {}, save_choices: {}, saved_detail_versions: {} };
    const prefill: Prefill = { form_revision: 1, event_date_revision: 1, values: { institution: "Saved school", accessibility_needs: "Step-free", date_of_birth: "2000-01-01" },
      saved_detail_versions: { institution: 2, accessibility_needs: 3 }, save_defaults: { accessibility_needs: true }, derivation_inputs: {} };
    expect(applyStageSuggestions(schema, value, prefill)).toEqual({ answers: { school: "My edit", access: "Step-free" }, derivations: {},
      save_choices: { accessibility_needs: false }, saved_detail_versions: { accessibility_needs: 3 } });
  });
  it("uses the frozen canonical UTC representation", () => {
    expect(utcInstant("2026-12-01T15:30:00+05:30")).toBe(contract.rsvp_identity.instant);
    expect(utcInstant("2026-12-01T10:00:00.123Z")).toBe("2026-12-01T10:00:00.123Z");
    expect(() => utcInstant("")).toThrow();
  });
});
