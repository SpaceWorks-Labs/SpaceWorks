import { describe, expect, it } from "vitest";

import type { MachineServiceRequest } from "../../../../generated/api";
import { cancelBody, estimateConsumed, runningHold } from "./cancelEstimate";
import { blankServiceDraft } from "./serviceDrafts";

const now = Date.parse("2026-10-21T10:00:00Z");
const running = { status: "in_progress", started_at: "2026-10-21T09:15:00Z", estimated_minutes: 60,
  planned_quantity: "40", planned_grams: "40", reserved_quantity: "40", reserved_grams: "40" } as unknown as MachineServiceRequest;

describe("cancel estimate (decision 61a)", () => {
  it("is elapsed / estimated x planned, in the hold's unit", () => {
    expect(estimateConsumed(running, now)).toBe("30.00");
  });
  it("never exceeds the hold", () => {
    expect(estimateConsumed({ ...running, estimated_minutes: 10 }, now)).toBe("40.00");
  });
  it("is empty when nothing is held, the job is waiting, or the duration is unknown", () => {
    expect(estimateConsumed({ ...running, reserved_quantity: "0", reserved_grams: "0" }, now)).toBe("");
    expect(estimateConsumed({ ...running, status: "accepted" }, now)).toBe("");
    expect(estimateConsumed({ ...running, estimated_minutes: 0 }, now)).toBe("");
    expect(runningHold({ ...running, status: "accepted" })).toBe(0);
  });
  it("sends a positive amount only for a held running job", () => {
    const values = { ...blankServiceDraft().actionValues, cancel_hold: "40", consumed_quantity: "12" };
    expect(cancelBody(values)).toEqual({ consumed_quantity: "12" });
    expect(cancelBody({ ...values, consumed_quantity: "0" })).toEqual({});
    expect(cancelBody({ ...values, cancel_hold: "", reason: "Stop" })).toEqual({ reason: "Stop" });
  });
});
