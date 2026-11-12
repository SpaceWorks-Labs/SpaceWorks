import { describe, expect, it } from "vitest";

import { reportFieldLabel } from "./reportFieldLabels";

describe("machine use by event report columns", () => {
  it("are labelled in words", () => {
    expect(reportFieldLabel("machine_minutes")).toBe("Machine minutes");
    expect(reportFieldLabel("approved_to_event")).toBe("Approved to the event");
    expect(reportFieldLabel("cost_decision")).toBe("Cost decision");
  });
});
