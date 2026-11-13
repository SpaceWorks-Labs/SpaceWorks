import { expect, it } from "vitest";
import profiles from "../../../../backend/tests/events/programme/contracts/fixtures/profile-fields-v3.json";
import bootstrap from "../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json";
import emergency from "../../../../backend/tests/events/programme/contracts/fixtures/emergency-contact-v2.json";
import { fields } from "./fieldPresentation";
import { parsePrefill, parseSavedDetails } from "./parsers";

it("represents every persistable standard key with matching sensitive choice metadata", () => {
  for (const descriptor of profiles.descriptors) {
    if (!descriptor.persistable || descriptor.field_key === "resume") continue;
    const field = fields.find(item => item.key === descriptor.field_key);
    expect(field).toBeDefined();
    expect(Boolean(field?.sensitive)).toBe(descriptor.sensitive);
  }
});

it("consumes the frozen zero-membership and compound emergency contracts", () => {
  expect(bootstrap.created_memberships).toBe(0);
  expect(bootstrap.prefill_request.context.subject_kind).toBe("application");
  expect(emergency.exact_keys).toEqual(["name", "relationship", "phone"]);
  expect(emergency.save_choices.emergency_contact).toBe(false);
  expect(parsePrefill(bootstrap.prefill_response)).toEqual(bootstrap.prefill_response);
  const compound = { ...emergency.prefill_round_trip, form_revision: 3, event_date_revision: 7, derivation_inputs: {} };
  expect(parsePrefill(compound)).toEqual(compound);
});

it("rejects numeric-age vault fields and preserves safe deletion versions", () => {
  expect(() => parseSavedDetails({ version: 1, readiness: "ready", fields: [{ field_key: "age_at_event", value: 22, version: 1, sensitive: true, default_save: false }] })).toThrow();
  expect(parseSavedDetails({ version: 2, readiness: "ready", fields: [{ field_key: "date_of_birth", value: null, version: 2, sensitive: true, default_save: false }] }).fields[0].version).toBe(2);
});
