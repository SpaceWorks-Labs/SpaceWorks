import { describe, expect, it } from "vitest";
import { teamStateLabel, applicationStateLabel } from "./labels";

describe("teamStateLabel", () => {
  it.each([
    ["forming", "Forming"],
    ["locked", "Locked"],
    ["disbanded", "Disbanded"],
  ])("%s reads %s", (code, text) => expect(teamStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(teamStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("applicationStateLabel", () => {
  it.each([
    ["draft", "Draft"],
    ["submitted", "Submitted"],
    ["offered", "Place offered"],
    ["waitlisted", "Waitlisted"],
    ["confirmed", "Confirmed"],
    ["rejected", "Not selected"],
    ["declined", "Declined"],
    ["expired", "Expired"],
    ["withdrawn", "Withdrawn"],
  ])("%s reads %s", (code, text) => expect(applicationStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(applicationStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

