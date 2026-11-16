import { describe, expect, it } from "vitest";
import { shareStateLabel, prizeStatusLabel, prizeKindLabel } from "./prizeLabels";

describe("shareStateLabel", () => {
  it.each([
    ["proposed", "Proposed"],
    ["confirmed", "Confirmed"],
    ["declined", "Declined"],
    ["forfeited", "Forfeited"],
  ])("%s reads %s", (code, text) => expect(shareStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(shareStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("prizeStatusLabel", () => {
  it.each([
    ["owed", "Owed"],
    ["part_paid", "Partly paid"],
    ["paid", "Paid"],
    ["fulfilled", "Handed over"],
    ["sponsor_paid", "Paid by sponsor"],
    ["forfeited", "Forfeited"],
    ["verified", "Verified"],
  ])("%s reads %s", (code, text) => expect(prizeStatusLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(prizeStatusLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("prizeKindLabel", () => {
  it.each([
    ["cash", "Cash"],
    ["item", "Item"],
    ["credit", "Credit"],
    ["perk", "Perk"],
  ])("%s reads %s", (code, text) => expect(prizeKindLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(prizeKindLabel("zz_unknown_code")).toBe("zz unknown code"));
});

