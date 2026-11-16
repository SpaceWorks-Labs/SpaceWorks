import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FreeQuotaPanel } from "./FreeQuotaPanel";
import type { FreeUsage, UsageSample } from "./types";

const sample = (over: Partial<UsageSample> = {}): UsageSample => ({ used: 10, cap: 100, uncertain: 0, unit: "recipients", state: "ok", source: "application",
  cap_source: "operator_configuration", cap_verified_on: null, scope: "deployment", sampled_at: "2026-10-18T00:00:00Z", reason_code: "", ...over });
const usage = (over: Partial<FreeUsage> = {}, tick: Partial<FreeUsage["tick"]> = {}): FreeUsage => ({ profile: "free", visibility: "deployment", database: sample({ unit: "bytes" }),
  objects: sample({ unit: "bytes" }), email: sample(), email_pending: 3, email_uncertain: 1, notices: [],
  tick: { last_completed_at: "2026-11-01T10:00:00Z", last_contact_at: "2026-11-01T10:01:00Z", age_seconds: 120, interval_seconds: 600, state: "ok", failed_tasks: 0, ...tick }, ...over });

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: false }));
afterEach(() => vi.useRealTimers());

describe("quota cards by visibility", () => {
  it("a deployment operator sees database, object and email cards", () => {
    render(<FreeQuotaPanel usage={usage()} />);
    expect(screen.getByRole("region", { name: "Database usage" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Object storage usage" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Email accepted today" })).toBeInTheDocument();
    expect(screen.getByText(/Pending email: 3\. Uncertain email: 1\./)).toBeInTheDocument();
  });
  it("omits the database card when there is none", () => {
    render(<FreeQuotaPanel usage={usage({ database: null })} />);
    expect(screen.queryByRole("region", { name: "Database usage" })).toBeNull();
  });
  it("a tenant sees only tenant-scoped samples and is told to contact the operator for email counts it cannot see", () => {
    render(<FreeQuotaPanel usage={usage({ visibility: "tenant", database: sample(), objects: sample({ scope: "tenant" }), email: sample({ scope: "provider_account" }) })} />);
    expect(screen.queryByRole("region", { name: "Database usage" })).toBeNull();
    expect(screen.getByRole("region", { name: "Object storage usage" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Email accepted today" })).toBeNull();
    expect(screen.getByText(/Pending email: Contact your operator\. Uncertain email: Contact your operator\./)).toBeInTheDocument();
  });
  it("a tenant with tenant-scoped email sees it, and Unknown for a missing count", () => {
    render(<FreeQuotaPanel usage={usage({ visibility: "tenant", objects: sample({ scope: "provider_account" }), email: sample({ scope: "tenant" }), email_pending: null, email_uncertain: null })} />);
    expect(screen.queryByRole("region", { name: "Object storage usage" })).toBeNull();
    expect(screen.getByRole("region", { name: "Email accepted today" })).toBeInTheDocument();
    expect(screen.getByText(/Pending email: Unknown\. Uncertain email: Unknown\./)).toBeInTheDocument();
  });
});

describe("email accounts", () => {
  it("shows caps, month charge and the provider-workload note; unknown caps read Unknown", () => {
    render(<FreeQuotaPanel usage={usage({ email_accounts: [
      { label: "Main", provider: "resend", accepted: 4, reserved: 1, uncertain: 0, daily_cap: 100, monthly_cap: 3000, monthly_charged: 40, reset_timezone: "UTC", provider_usage_known: true },
      { label: "Backup", provider: "ses", accepted: 0, reserved: 0, uncertain: 0, daily_cap: null, monthly_cap: null, monthly_charged: 0, reset_timezone: "Asia/Kolkata", provider_usage_known: false },
    ] })} />);
    expect(screen.getByText("Main (resend)")).toBeInTheDocument();
    expect(screen.getByText("Daily cap: 100. Month charged: 40 / 3000. Reset timezone: UTC.")).toBeInTheDocument();
    expect(screen.getByText("Other provider workloads: Included.")).toBeInTheDocument();
    expect(screen.getByText("Daily cap: Unknown. Month charged: 0 / Unknown. Reset timezone: Asia/Kolkata.")).toBeInTheDocument();
  });
});

describe("notification and failure callouts", () => {
  it("warns about uncertain notification outcomes only when there are some", () => {
    const { unmount } = render(<FreeQuotaPanel usage={usage({ notification_uncertain: 4 })} />);
    expect(screen.getByText("Some notification outcomes are uncertain.")).toBeInTheDocument();
    expect(screen.getByText(/4 delivery claims need operator review/)).toBeInTheDocument();
    unmount();
    render(<FreeQuotaPanel usage={usage({ notification_uncertain: 0 })} />);
    expect(screen.queryByText("Some notification outcomes are uncertain.")).toBeNull();
  });
  it("flags failed scheduled work with a danger callout", () => {
    render(<FreeQuotaPanel usage={usage({}, { failed_tasks: 2 })} />);
    expect(screen.getByText("Some scheduled work failed.")).toBeInTheDocument();
    expect(screen.getByText("Review job failures and backlog even if the trigger connected recently.")).toBeInTheDocument();
    expect(screen.getByText(/Failed tasks: 2\./)).toBeInTheDocument();
  });
});

describe("scheduler tick status", () => {
  it("a recent completion within three intervals is healthy with the interval in minutes", () => {
    render(<FreeQuotaPanel usage={usage()} />);
    expect(screen.getByText("Recent completion")).toBeInTheDocument();
    expect(screen.getByText("Minutes since last successful tick: 2. Configured interval: 10 minutes.")).toBeInTheDocument();
    expect(screen.queryByText(/Ask the operator to check the trigger/)).toBeNull();
  });
  it("goes Overdue as time passes on the screen beyond three intervals, and asks the operator to check", () => {
    render(<FreeQuotaPanel usage={usage({}, { age_seconds: 1700 })} />);
    expect(screen.getByText("Recent completion")).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(180_000); });
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText(/Ask the operator to check the trigger, provider pause status and job failures/)).toBeInTheDocument();
    expect(screen.getByText(/Minutes since last successful tick: 31\./)).toBeInTheDocument();
  });
  it("never run reads Never run, and an unknown state reads Unknown completion", () => {
    const { unmount } = render(<FreeQuotaPanel usage={usage({}, { state: "never", last_completed_at: null, age_seconds: null })} />);
    expect(screen.getByText("Never run")).toBeInTheDocument();
    expect(screen.getByText(/Minutes since last successful tick: Unknown\./)).toBeInTheDocument();
    unmount();
    render(<FreeQuotaPanel usage={usage({}, { state: "unknown" })} />);
    expect(screen.getByText("Unknown completion")).toBeInTheDocument();
  });
  it("a missing or negative server age cannot be trusted and counts as unknown", () => {
    const { unmount } = render(<FreeQuotaPanel usage={usage({}, { age_seconds: -5 })} />);
    expect(screen.getByText("Unknown completion")).toBeInTheDocument();
    unmount();
    render(<FreeQuotaPanel usage={usage({}, { last_completed_at: null, age_seconds: 30, state: "failed" })} />);
    expect(screen.getByText("Unknown completion")).toBeInTheDocument();
  });
  it("an invalid interval reads Unknown and marks the tick stale", () => {
    render(<FreeQuotaPanel usage={usage({}, { interval_seconds: 0 })} />);
    expect(screen.getByText(/Configured interval: Unknown\./)).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });
  it("does not show the last-contact time as a fact when the server sent none", () => {
    render(<FreeQuotaPanel usage={usage({}, { last_contact_at: null })} />);
    expect(screen.getByText(/Last trigger contact: Unknown\./)).toBeInTheDocument();
  });
});
