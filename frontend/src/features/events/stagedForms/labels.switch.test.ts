import { describe, expect, it } from "vitest";
import { stageNameLabel, stageDefinitionStateLabel, stageAssignmentStateLabel, stageBlockedActionLabel, stageScheduleModeLabel } from "./labels";

describe("stageNameLabel", () => {
  it.each([
    ["application", "Application"],
    ["shortlisted", "Shortlisted"],
    ["accepted_rsvp", "Accepted and RSVP"],
    ["pre_event", "Before the event"],
    ["post_event", "After the event"],
  ])("%s reads %s", (code, text) => expect(stageNameLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(stageNameLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("stageDefinitionStateLabel", () => {
  it.each([
    ["draft", "Draft"],
    ["published", "Published"],
    ["retired", "Retired"],
  ])("%s reads %s", (code, text) => expect(stageDefinitionStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(stageDefinitionStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("stageAssignmentStateLabel", () => {
  it.each([
    ["scheduled", "Scheduled"],
    ["open", "Open"],
    ["completed", "Completed"],
    ["overdue", "Overdue"],
    ["cancelled", "Cancelled"],
  ])("%s reads %s", (code, text) => expect(stageAssignmentStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(stageAssignmentStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("stageBlockedActionLabel", () => {
  it.each([
    ["rsvp", "RSVP"],
    ["check_in", "Check-in"],
    ["claim_submit", "Submitting a claim"],
  ])("%s reads %s", (code, text) => expect(stageBlockedActionLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(stageBlockedActionLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("stageScheduleModeLabel", () => {
  it.each([
    ["trigger", "When the stage starts"],
    ["absolute", "At a set date and time"],
    ["after_trigger", "A set time after the stage starts"],
    ["event_start", "Relative to the event start"],
    ["event_end", "Relative to the event end"],
  ])("%s reads %s", (code, text) => expect(stageScheduleModeLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(stageScheduleModeLabel("zz_unknown_code")).toBe("zz unknown code"));
});

