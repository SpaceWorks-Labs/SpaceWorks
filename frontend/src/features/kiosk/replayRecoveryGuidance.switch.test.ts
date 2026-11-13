import { describe, expect, it } from "vitest";
import { kioskOperationLabel, kioskCommandStatusLabel } from "./replayRecoveryGuidance";

describe("kioskOperationLabel", () => {
  it.each([
    ["assign_box", "Assign box"],
    ["reviewed_issue", "Issue request"],
    ["reviewed_return", "Return request"],
    ["direct_handout", "Direct handout"],
    ["direct_return", "Direct return"],
  ])("%s reads %s", (code, text) => expect(kioskOperationLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(kioskOperationLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("kioskCommandStatusLabel", () => {
  it.each([
    ["queued", "Queued"],
    ["preparing", "Preparing"],
    ["uploading", "Uploading"],
    ["executing", "Sending"],
    ["succeeded", "Confirmed"],
    ["failed", "Failed"],
  ])("%s reads %s", (code, text) => expect(kioskCommandStatusLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(kioskCommandStatusLabel("zz_unknown_code")).toBe("zz unknown code"));
});

