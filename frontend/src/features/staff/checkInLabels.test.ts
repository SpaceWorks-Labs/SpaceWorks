import { describe, expect, it } from "vitest";

import { offlineSyncOutcomeLabel } from "./checkInLabels";
import { limitHint, limitLabel } from "./platformSpaces/limitCopy";

describe("offline check-in outcome labels (EV-27)", () => {
  it("words every minor-clearance refusal instead of showing the raw code", () => {
    for (const code of ["guardian_consent_required", "guardian_consent_expired", "guardian_terms_missing", "minor_not_admitted", "minor_below_minimum_age"]) {
      const label = offlineSyncOutcomeLabel(code);
      expect(label).not.toBe(code.replace(/_/g, " "));
      expect(label).not.toContain("_");
    }
    expect(offlineSyncOutcomeLabel("guardian_consent_required")).toBe("A guardian's consent is needed first");
  });
});

describe("webhook endpoint limit copy (LM-3)", () => {
  it("names the limit and says what happens at it", () => {
    expect(limitLabel("webhook_endpoints", "webhook_endpoints")).toBe("Outbound webhook endpoints");
    expect(limitHint("webhook_endpoints")).toMatch(/no new endpoints/);
  });
});
