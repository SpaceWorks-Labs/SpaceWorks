import { describe, expect, it } from "vitest";
import { bookingStatusLabel, spaceKindLabel } from "./bookingStatusLabel";

describe("bookingStatusLabel", () => {
  it.each([
    ["pending", "Pending"],
    ["confirmed", "Confirmed"],
    ["rejected", "Rejected"],
    ["cancelled", "Cancelled"],
    ["completed", "Completed"],
    ["no_show", "No-show"],
  ])("%s reads %s", (code, text) => expect(bookingStatusLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(bookingStatusLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("spaceKindLabel", () => {
  it.each([
    ["dev_room", "Development room"],
    ["bench", "Bench"],
    ["meeting", "Meeting room"],
    ["other", "Other"],
    ["machine", "Machine time"],
  ])("%s reads %s", (code, text) => expect(spaceKindLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(spaceKindLabel("zz_unknown_code")).toBe("zz unknown code"));
});

