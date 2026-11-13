import { describe, expect, it } from "vitest";

import { NOT_FOUND_MESSAGE, StructuredApiError } from "./errors";

describe("StructuredApiError", () => {
  it("replaces Django's model-naming 404 with plain words", () => {
    const error = new StructuredApiError(404, { detail: "No MakerspaceMembership matches the given query." });
    expect(error.message).toBe(NOT_FOUND_MESSAGE);
    expect(error.message).not.toMatch(/MakerspaceMembership/);
  });

  it("keeps a deliberate 404 message and other statuses untouched", () => {
    expect(new StructuredApiError(404, { detail: "This event was cancelled." }).message).toBe("This event was cancelled.");
    expect(new StructuredApiError(403, { detail: "No MakerspaceMembership matches the given query." }).message)
      .toBe("No MakerspaceMembership matches the given query.");
  });
});
