import { describe, expect, it } from "vitest";
import { registrationStatusLabel } from "./registrationLabels";

describe("registrationStatusLabel", () => {
  it.each([
    ["pending_approval", "Awaiting approval"],
    ["registered", "Confirmed"],
    ["waitlisted", "Waitlisted"],
    ["rejected", "Not approved"],
    ["cancelled", "Cancelled"],
    ["attended", "Attended"],
  ])("%s reads %s", (code, text) => expect(registrationStatusLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(registrationStatusLabel("zz_unknown_code")).toBe("zz unknown code"));
});

