import { describe, expect, it } from "vitest";
import { waiverStateLabel, offlineSyncOutcomeLabel } from "./checkInLabels";

describe("waiverStateLabel", () => {
  it.each([
    ["not_required", "not required"],
    ["current", "on file"],
    ["on_file", "on file"],
    ["missing", "missing"],
  ])("%s reads %s", (code, text) => expect(waiverStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(waiverStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("offlineSyncOutcomeLabel", () => {
  it.each([
    ["applied", "Checked in"],
    ["already_attended", "Already checked in"],
    ["duplicate_operation", "Already sent"],
    ["event_unavailable", "Event is not available"],
    ["invalid_token", "Ticket code not recognised"],
    ["outside_window", "Outside the check-in window"],
    ["registration_changed", "Registration changed since the roster was downloaded"],
    ["stage_incomplete", "A required stage form is not complete"],
    ["guardian_consent_required", "A guardian's consent is needed first"],
    ["guardian_consent_expired", "The guardian's consent has expired"],
    ["guardian_terms_missing", "The guardian has not accepted the current terms"],
    ["minor_not_admitted", "This space does not admit people under the adult age"],
    ["minor_below_minimum_age", "Below this space's minimum age"],
  ])("%s reads %s", (code, text) => expect(offlineSyncOutcomeLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(offlineSyncOutcomeLabel("zz_unknown_code")).toBe("zz unknown code"));
});

