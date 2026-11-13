import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { moduleLabel, moduleList, workflowLabel } from "./moduleLabels";
import { reportFieldLabel } from "../features/staff/panels/reportFieldLabels";
import { limitLabel } from "../features/staff/platformSpaces/limitCopy";

describe("translated key labels", () => {
  it("names every registered module key, never its raw snake_case", () => {
    const api = readFileSync(join(process.cwd(), "src", "generated", "api.ts"), "utf8");
    const declared = /export type ModulesEnum = ([^;]+);/.exec(api)?.[1] ?? "";
    const keys = [...declared.matchAll(/"([a-z_]+)"/g)].map((match) => match[1]);
    expect(keys.length).toBeGreaterThanOrEqual(30);
    for (const key of keys) expect(moduleLabel(key)).not.toMatch(/_/);
    expect(moduleLabel("qr_management")).toBe("QR management");
    expect(moduleLabel("webhook")).toBe("Signed webhooks");
  });

  it("falls back to words for a retired or unknown key", () => {
    expect(moduleLabel("procurement")).toBe("Procurement");
    expect(moduleLabel("some_new_module")).toBe("Some new module");
    expect(moduleList(["events", "member_accounts"])).toBe("Events, Member accounts");
    expect(workflowLabel("qr_print_batch")).toBe("QR print batches");
    expect(workflowLabel("brand_new_flow")).toBe("Brand new flow");
  });

  it("labels report columns and usage resources, with the key's words only as a fallback", () => {
    expect(reportFieldLabel("makerspace_id")).toBe("Space ID");
    expect(reportFieldLabel("attendance_rate_percent")).toBe("Attendance rate (%)");
    expect(reportFieldLabel("brand_new_column")).toBe("Brand new column");
    expect(limitLabel("bookings", "active bookings")).toBe("Active bookings");
    expect(limitLabel("otp_sms", "")).toBe("Sign-in code texts per day");
    expect(limitLabel("future_key", "future things")).toBe("Future things");
  });
});
