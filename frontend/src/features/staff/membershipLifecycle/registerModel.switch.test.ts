import { describe, expect, it } from "vitest";
import { rowResultLabel } from "./registerModel";

describe("rowResultLabel", () => {
  it.each([
    ["not_found", "Not in your scope or no longer a member"],
    ["not_due", "Not due for a reminder today"],
    ["no_card", "Holds no card"],
    ["not_sent", "Card email not sent (limit or rule)"],
    ["quota_exceeded", "Limit reached"],
    ["permission_denied", "Not allowed"],
  ])("%s reads %s", (code, text) => expect(rowResultLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(rowResultLabel("zz_unknown_code")).toBe("zz unknown code"));
});

