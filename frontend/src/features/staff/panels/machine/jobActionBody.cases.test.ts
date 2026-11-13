import { describe, expect, it } from "vitest";
import { initialJobValues, jobActionBody, jobFormBlocker, type JobFormValues } from "./jobActionBody";

const values = (over: Partial<JobFormValues> = {}): JobFormValues => ({ ...initialJobValues({ estimated_minutes: 0 } as never), ...over });
const printer = { hasPool: true, printer: true };
const other = { hasPool: true, printer: false };
const none = { hasPool: false, printer: false };

describe("initialJobValues", () => {
  it("prefers the staff estimate, then the member's, then 60 minutes", () => {
    expect(initialJobValues({ estimated_minutes: 45, member_estimate_minutes: 30 } as never).estimated_minutes).toBe("45");
    expect(initialJobValues({ estimated_minutes: 0, member_estimate_minutes: 30 } as never).estimated_minutes).toBe("30");
    expect(initialJobValues({} as never).estimated_minutes).toBe("60");
  });
  it("seeds the machine from the preassignment and the pickup location from the job", () => {
    const initial = initialJobValues({ preassigned_machine_id: 8, pickup_location: "Shelf 2", estimated_minutes: 20 } as never);
    expect(initial).toMatchObject({ machine_id: "8", pickup_location: "Shelf 2", actual_minutes: "20", percent_complete: "0", override_length: false });
    expect(initialJobValues({} as never)).toMatchObject({ machine_id: "", pickup_location: "", actual_minutes: "0" });
  });
});

describe("jobActionBody", () => {
  it("accept sends the estimate, planned grams only for printers with a pool, and the length override only when ticked", () => {
    expect(jobActionBody("accept", values({ estimated_minutes: "30", quantity: "50" }), printer)).toEqual({ estimated_minutes: 30, planned_grams: "50" });
    expect(jobActionBody("accept", values({ estimated_minutes: "30", quantity: "50" }), other)).toEqual({ estimated_minutes: 30 });
    expect(jobActionBody("accept", values({ estimated_minutes: "30", quantity: "50" }), { hasPool: false, printer: true })).toEqual({ estimated_minutes: 30 });
    expect(jobActionBody("accept", values({ estimated_minutes: "", override_length: true }), none)).toEqual({ estimated_minutes: 0, override_length: true });
  });
  it("start names the machine and pool, using grams for printers and quantity otherwise", () => {
    expect(jobActionBody("start", values({ machine_id: "3", consumable_pool_id: "9", estimated_minutes: "15", quantity: " 40 " }), printer))
      .toEqual({ machine_id: 3, consumable_pool_id: 9, estimated_minutes: 15, planned_grams: "40" });
    expect(jobActionBody("start", values({ machine_id: "3", consumable_pool_id: "9", quantity: "2" }), other)).toMatchObject({ planned_quantity: "2" });
    expect(jobActionBody("start", values({ machine_id: "", consumable_pool_id: "9", quantity: "2" }), none)).toEqual({ machine_id: null, consumable_pool_id: undefined, estimated_minutes: 60, planned_quantity: undefined });
  });
  it("quote sends nulls for an absent quantity or pool, the trimmed note, and estimates only when given", () => {
    expect(jobActionBody("quote", values({ estimated_minutes: "10", note: " n " }), none)).toEqual({ estimated_minutes: 10, quantity: null, consumable_pool_id: null, note: "n" });
    const entries = [{ id: 1 }] as never;
    expect(jobActionBody("quote", values({ quantity: "3", consumable_pool_id: "4" }), { ...other, entries })).toMatchObject({ quantity: "3", consumable_pool_id: 4, consumable_estimates: entries });
    expect(jobActionBody("quote", values(), { ...other, entries: [] })).not.toHaveProperty("consumable_estimates");
  });
  it("request-changes sends the code and the trimmed message", () => expect(jobActionBody("request-changes", values({ code: "bad_file", message: " fix it " }), none)).toEqual({ code: "bad_file", message: "fix it" }));
  it("reject sends the trimmed reason and the code only when chosen", () => {
    expect(jobActionBody("reject", values({ reason: " no " }), none)).toEqual({ reason: "no" });
    expect(jobActionBody("reject", values({ reason: "no", code: "unsafe" }), none)).toEqual({ reason: "no", code: "unsafe" });
  });
  it("complete sends the real minutes, the actual grams or quantity and the pickup location", () => {
    expect(jobActionBody("complete", values({ actual_minutes: "25", quantity: "31", pickup_location: " Shelf " }), printer)).toEqual({ actual_minutes: 25, actual_grams: "31", pickup_location: "Shelf" });
    expect(jobActionBody("complete", values({ actual_minutes: "25", quantity: "3" }), other)).toMatchObject({ actual_quantity: "3" });
    expect(jobActionBody("complete", values(), { ...none, entries: [{ id: 2 }] as never })).toHaveProperty("profile_consumptions");
  });
  it("fail sends the percentage and optional code and fault", () => {
    expect(jobActionBody("fail", values({ actual_minutes: "5", percent_complete: "40", reason: " jam ", code: "jam", fault: "nozzle" }), printer))
      .toEqual({ actual_minutes: 5, actual_grams: undefined, percent_complete: 40, reason: "jam", code: "jam", fault: "nozzle" });
    const bare = jobActionBody("fail", values({ reason: "x" }), none);
    expect(bare).not.toHaveProperty("code");
    expect(bare).not.toHaveProperty("fault");
  });
  it("collect trims the pickup code and collector name", () => expect(jobActionBody("collect", values({ pickup_code: " 1234 ", collector_name: " Ann " }), none)).toEqual({ pickup_code: "1234", collector_name: "Ann" }));
  it("urgent always sets the flag with the trimmed reason", () => expect(jobActionBody("urgent", values({ reason: " now " }), none)).toEqual({ urgent: true, reason: "now" }));
  it("assign sends the machine id or null", () => {
    expect(jobActionBody("assign", values({ machine_id: "6" }), none)).toEqual({ machine_id: 6 });
    expect(jobActionBody("assign", values({ machine_id: "" }), none)).toEqual({ machine_id: null });
  });
});

describe("jobFormBlocker", () => {
  it("needs a reason code and message to request changes", () => {
    expect(jobFormBlocker("request-changes", values({ message: "m" }))).toBe("Choose a reason and write a message.");
    expect(jobFormBlocker("request-changes", values({ code: "c", message: "  " }))).toBe("Choose a reason and write a message.");
    expect(jobFormBlocker("request-changes", values({ code: "c", message: "m" }))).toBeNull();
  });
  it.each(["reject", "fail", "urgent"] as const)("needs a reason to %s", (action) => {
    expect(jobFormBlocker(action, values({ reason: "  " }))).toBe("Add a reason.");
    expect(jobFormBlocker(action, values({ reason: "because" }))).toBeNull();
  });
  it("needs a machine to start", () => {
    expect(jobFormBlocker("start", values({ machine_id: "" }))).toBe("Choose a machine.");
    expect(jobFormBlocker("start", values({ machine_id: "1", estimated_minutes: "10" }))).toBeNull();
  });
  it.each(["accept", "start", "quote"] as const)("needs valid estimated minutes to %s, accepting zero", (action) => {
    const base = { machine_id: "1" };
    expect(jobFormBlocker(action, values({ ...base, estimated_minutes: "" }))).toBe("Enter the estimated minutes.");
    expect(jobFormBlocker(action, values({ ...base, estimated_minutes: "-1" }))).toBe("Enter the estimated minutes.");
    expect(jobFormBlocker(action, values({ ...base, estimated_minutes: "abc" }))).toBe("Enter the estimated minutes.");
    expect(jobFormBlocker(action, values({ ...base, estimated_minutes: "0" }))).toBeNull();
  });
  it("has no blocker for actions that need no input", () => {
    for (const action of ["complete", "collect", "assign"] as const) expect(jobFormBlocker(action, values({ estimated_minutes: "" }))).toBeNull();
  });
});
