import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FreeQuotaPanel } from "./FreeQuotaPanel";
import { quotaState } from "./QuotaCard";
import type { FreeUsage, UsageSample } from "./types";

const sample: UsageSample = { used: 10, cap: 100, uncertain: 90, unit: "recipients", state: "reached",
  source: "application", cap_source: "operator_configuration", cap_verified_on: null,
  scope: "provider_account", sampled_at: "2026-10-18T00:00:00Z", reason_code: "provider_external_usage_unknown" };

describe("free account capacity", () => {
  it("counts reserved capacity once alongside accepted usage", () => {
    expect(quotaState(sample)).toBe("Reached");
  });
  it("shows accepted, reserved, uncertain and outside-account uncertainty separately", () => {
    const usage: FreeUsage = { profile: "free", visibility: "deployment", database: null,
      objects: { ...sample, unit: "bytes", scope: "deployment" }, email: sample,
      email_pending: 7, email_uncertain: 5, notices: [],
      email_accounts: [{ label: "Email account 1", provider: "resend", accepted: 10,
        reserved: 85, uncertain: 5, daily_cap: 100, monthly_cap: 3000, monthly_charged: 100,
        reset_timezone: "UTC", provider_usage_known: false }],
      tick: { last_completed_at: null, last_contact_at: null, age_seconds: null,
        interval_seconds: 600, state: "never", failed_tasks: 0 } };
    render(<FreeQuotaPanel usage={usage} />);
    expect(screen.getByText("Accepted today: 10. Reserved: 85. Uncertain: 5.")).toBeInTheDocument();
    expect(screen.getByText(/Other provider workloads: Unknown/)).toBeInTheDocument();
  });
});
