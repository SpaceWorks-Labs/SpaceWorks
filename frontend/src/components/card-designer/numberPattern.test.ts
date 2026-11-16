import { describe, expect, it } from "vitest";

import { MEMBER_TOKENS, STAFF_TOKENS, patternProblem, renderPattern, samplesOf } from "./numberPattern";

describe("card number patterns", () => {
  it("accepts an empty pattern as no scheme", () => {
    expect(patternProblem("", "")).toBeNull();
    expect(samplesOf("", "")).toEqual([]);
  });

  it("renders sequence, year and prefix tokens like the server", () => {
    expect(renderPattern("{PREFIX}-{YYYY}-{SEQ:4}", "TNK", 42, 2026)).toBe("TNK-2026-0042");
    expect(renderPattern("{PREFIX}{YY}{SEQ}", "AB", 7, 2026)).toBe("AB267");
    expect(samplesOf("tnk", "{prefix}-{seq:3}")).toEqual(["TNK-001", "TNK-002", "TNK-003"]);
  });

  it("says what is wrong in plain words", () => {
    expect(patternProblem("T", "{SEQ}")?.message).toBe("Use 2 to 6 capital letters or digits.");
    expect(patternProblem("TNK", "ABC")?.message).toBe("Use {SEQ} or {SEQ:n} exactly once.");
    expect(patternProblem("TNK", "{SEQ}{SEQ}")?.message).toBe("Use {SEQ} or {SEQ:n} exactly once.");
    expect(patternProblem("TNK", "{YYYY:2}-{SEQ}")?.message).toBe("Only {SEQ} and {MEMBER} take a width.");
    expect(patternProblem("", "{PREFIX}-{SEQ}")).toEqual({ field: "prefix", message: "Add a prefix, or remove {PREFIX} from the pattern." });
    expect(patternProblem("TNK", "{SEQ} #")?.message).toBe("Use capital letters, digits, spaces and . / _ - around the tokens.");
  });

  it("refuses a number longer than 32 characters", () => {
    expect(patternProblem("TNK", "LONGLITERALTEXTLONGLITERAL-{SEQ:8}")?.message).toBe("A number can be at most 32 characters long.");
  });

  it("keeps member and unit tokens out of staff schemes", () => {
    expect(patternProblem("STF", "{PREFIX}-{MEMBER:4}-{SEQ}", STAFF_TOKENS)?.message).toBe("That token is not available here.");
    expect(patternProblem("TNK", "{UNIT}-{SEQ}", MEMBER_TOKENS)).toBeNull();
  });
});
