import { describe, expect, it } from "vitest";
import { authErrorMessage } from "./authErrorCopy";
import { PLAN_LIMIT_MESSAGE, SPACE_READ_ONLY_MESSAGE, StructuredApiError } from "./errors";

describe("space refusal copy", () => {
  it("explains a read-only space instead of the raw server text", () => {
    const error = new StructuredApiError(423, { detail: "Locked.", code: "space_read_only" });
    expect(error.message).toBe(SPACE_READ_ONLY_MESSAGE);
    expect(authErrorMessage(error)).toBe(SPACE_READ_ONLY_MESSAGE);
    expect(error.code).toBe("space_read_only");
  });

  it("keeps the plan's own limit sentence and adds what to do", () => {
    const error = new StructuredApiError(400, { limit: "Your plan allows 100 members.", code: "plan_limit_reached" });
    expect(error.message).toBe(`Your plan allows 100 members. ${PLAN_LIMIT_MESSAGE}`);
  });

  it("reads the DRF list shape of a plan limit refusal", () => {
    const error = new StructuredApiError(400, { limit: ["Your plan allows 5 machines."], code: ["plan_limit_reached"] });
    expect(error.message).toBe(`Your plan allows 5 machines. ${PLAN_LIMIT_MESSAGE}`);
  });

  it("leaves other errors alone", () => {
    expect(new StructuredApiError(400, { limit: ["Must be positive."] }).message).toBe("Must be positive.");
    expect(new StructuredApiError(409, { detail: "Conflict.", code: "space_not_active" }).message).toBe("Conflict.");
  });
});
