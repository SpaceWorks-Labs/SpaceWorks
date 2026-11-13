import { describe, expect, it } from "vitest";
import { payoutStateLabel, payoutEligibilityLabel } from "./labels";

describe("payoutStateLabel", () => {
  it.each([
    ["open", "Open"],
    ["settled", "Settled"],
    ["cancelled", "Cancelled"],
  ])("%s reads %s", (code, text) => expect(payoutStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(payoutStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("payoutEligibilityLabel", () => {
  it.each([
    ["eligible", "Eligible"],
    ["held", "Held"],
    ["needs_acknowledgement", "Needs acknowledgement"],
  ])("%s reads %s", (code, text) => expect(payoutEligibilityLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(payoutEligibilityLabel("zz_unknown_code")).toBe("zz unknown code"));
});

