import { describe, expect, it } from "vitest";

import { initialJobValues, jobActionBody, jobFormBlocker } from "./jobActionBody";
import type { StaffJob } from "./machineJobsApi";
import { machineStatusLabel } from "./machineStatusLabel";

const job = { id: 1, status: "pending", estimated_minutes: 0, member_estimate_minutes: 45, preassigned_machine_id: 3, pickup_location: "" } as unknown as StaffJob;

describe("jobActionBody", () => {
  it("prefills from the member estimate and the pre-assigned machine", () => {
    const values = initialJobValues(job);
    expect(values.estimated_minutes).toBe("45");
    expect(values.machine_id).toBe("3");
  });

  it("uses gram fields for printers and quantity fields for other types", () => {
    const values = { ...initialJobValues(job), quantity: "12", consumable_pool_id: "7" };
    expect(jobActionBody("start", values, { hasPool: true, printer: true })).toMatchObject({ machine_id: 3, consumable_pool_id: 7, planned_grams: "12" });
    expect(jobActionBody("start", values, { hasPool: true, printer: false })).toMatchObject({ planned_quantity: "12" });
    expect(jobActionBody("complete", { ...values, pickup_location: " Shelf B " }, { hasPool: false, printer: false })).toEqual({ actual_minutes: 0, actual_quantity: undefined, pickup_location: "Shelf B" });
  });

  it("sends fail code and fault, and the override only when ticked", () => {
    const values = { ...initialJobValues(job), code: "nozzle_jam", fault: "space", reason: "Jammed", percent_complete: "40" };
    expect(jobActionBody("fail", values, { hasPool: false, printer: true })).toMatchObject({ code: "nozzle_jam", fault: "space", percent_complete: 40, reason: "Jammed" });
    expect(jobActionBody("accept", values, { hasPool: false, printer: false })).toEqual({ estimated_minutes: 45 });
    expect(jobActionBody("accept", { ...values, override_length: true }, { hasPool: false, printer: false })).toEqual({ estimated_minutes: 45, override_length: true });
  });

  it("blocks incomplete forms", () => {
    const values = initialJobValues(job);
    expect(jobFormBlocker("request-changes", values)).toMatch(/reason/);
    expect(jobFormBlocker("reject", values)).toMatch(/reason/);
    expect(jobFormBlocker("collect", values)).toBeNull();
  });
});

describe("machineStatusLabel", () => {
  it("names the new job statuses for staff", () => {
    expect(machineStatusLabel("changes_requested")).toBe("Needs changes");
    expect(machineStatusLabel("quoted")).toBe("Quote sent");
    expect(machineStatusLabel("uncollected")).toBe("Not collected");
    expect(machineStatusLabel("in_progress")).toBe("In progress");
  });
});
