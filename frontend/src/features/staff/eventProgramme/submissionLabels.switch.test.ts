import { describe, expect, it } from "vitest";
import { submissionStateLabel, assetStateLabel, triageLabel } from "./submissionLabels";

describe("submissionStateLabel", () => {
  it.each([
    ["draft", "Draft"],
    ["submitted", "Submitted"],
    ["locked", "Locked"],
    ["withdrawn", "Withdrawn"],
    ["disqualified", "Disqualified"],
  ])("%s reads %s", (code, text) => expect(submissionStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(submissionStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("assetStateLabel", () => {
  it.each([
    ["reserved", "Reserved"],
    ["uploaded", "Uploaded"],
    ["validating", "Checking"],
    ["copying", "Copying"],
    ["ready", "Ready"],
    ["deleting", "Deleting"],
    ["rejected", "Rejected"],
  ])("%s reads %s", (code, text) => expect(assetStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(assetStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("triageLabel", () => {
  it.each([
    ["pending", "Pending"],
    ["eligible", "Eligible"],
    ["ineligible", "Ineligible"],
    ["hidden", "Hidden"],
  ])("%s reads %s", (code, text) => expect(triageLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(triageLabel("zz_unknown_code")).toBe("zz unknown code"));
});

