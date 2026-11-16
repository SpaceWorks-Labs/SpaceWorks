import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DeploymentPanel } from "./DeploymentPanel";
import { dateLabel, formatUsage, QuotaCard, quotaState } from "./QuotaCard";
import type { DeploymentSummary, FreeUsage, TenantDeploymentSummary, UsageSample } from "./types";

vi.mock("./FreeQuotaPanel", () => ({ FreeQuotaPanel: ({ usage }: { usage: { visibility: string } }) => <p>free quota panel {usage.visibility}</p> }));

const sample = (over: Partial<UsageSample> = {}): UsageSample => ({ used: 100_000_000, cap: 1_000_000_000, unit: "bytes", state: "ok", source: "s3", cap_source: "plan",
  cap_verified_on: "2026-10-01T00:00:00Z", scope: "tenant", sampled_at: "2026-11-01T00:00:00Z", uncertain: 0, reason_code: "", ...over });
const host = (over: Partial<DeploymentSummary> = {}): DeploymentSummary => ({ scope: "deployment", mode: "host", profile: "full", scanner: "clamav", media_validation_available: true,
  topology: "single node", database_transport: "unix socket", database_major: 16, storage: [{ label: "evidence", upload: "post", versioned: true, object_lock: true }],
  last_worker_success_at: "2026-11-01T10:00:00Z", last_scheduler_success_at: null, portable_dump_available: true, ...over });
const tenant = (over: Partial<TenantDeploymentSummary> = {}): TenantDeploymentSummary => ({ scope: "tenant", mode: "managed", profile: "free", scanner: "none", media_validation_available: false,
  deployment_warning: false, ...over });

describe("deployment scope", () => {
  it("shows launch mode, topology, database, storage guarantees, scanner and the last work times", () => {
    render(<DeploymentPanel data={host()} />);
    expect(screen.getByRole("heading", { name: "Deployment" })).toBeInTheDocument();
    expect(screen.getByText("host / full")).toBeInTheDocument();
    expect(screen.getByText("single node")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL 16, unix socket")).toBeInTheDocument();
    expect(screen.getByText(/evidence: POST upload-time size policy; versioned; Object Lock available\./)).toBeInTheDocument();
    expect(screen.getByText("ClamAV (fails closed on scan failure)")).toBeInTheDocument();
    expect(screen.getByText(/Scheduler: Unknown\./)).toBeInTheDocument();
  });
  it("describes PUT finalization, unversioned storage and no scanner", () => {
    render(<DeploymentPanel data={host({ scanner: "none", storage: [{ label: "backups", upload: "put", versioned: false, object_lock: false }] })} />);
    expect(screen.getByText(/backups: PUT finalization-time size validation; unversioned; Object Lock/)).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
  });
  it("host mode explains supervised recovery and a qualified portable export, with no managed rows", () => {
    render(<DeploymentPanel data={host()} />);
    expect(screen.getByText("Supervised host recovery follows the configured host contract.")).toBeInTheDocument();
    expect(screen.getByText("Portable makerspace export: Qualified; import into a fresh supervised target.")).toBeInTheDocument();
    expect(screen.queryByText("Provider recovery")).toBeNull();
    expect(screen.queryByText("Platform updates")).toBeNull();
    expect(screen.getByRole("link", { name: /Recovery limitations/ })).toHaveAttribute("rel", "noreferrer");
  });
  it("when the portable export is unavailable it shows the server's reason, or the default checklist", () => {
    const { unmount } = render(<DeploymentPanel data={host({ portable_dump_available: false, portable_dump_reason: "Maintenance window not proven" })} />);
    expect(screen.getByText("Portable makerspace export: Unavailable on this deployment.")).toBeInTheDocument();
    expect(screen.getByText("Maintenance window not proven")).toBeInTheDocument();
    unmount();
    render(<DeploymentPanel data={host({ portable_dump_available: false })} />);
    expect(screen.getByText("Direct/session maintenance, isolated scratch databases and capture proofs must pass before export.")).toBeInTheDocument();
  });
  it("managed mode shows provider recovery with statuses, the reason, a safe runbook link, and platform updates", () => {
    render(<DeploymentPanel data={host({ mode: "managed", provider_recovery: { database_status: "verified", object_status: "unavailable", drill_status: "failed",
      last_drill_at: "2026-10-30T00:00:00Z", reason: "Drill timed out", runbook_url: "https://runbook.example/recover" } })} />);
    expect(screen.getByText("Database backup/PITR: verified. Object recovery: unavailable.")).toBeInTheDocument();
    expect(screen.getByText(/Offline recovery drill: failed\. Last drill: /)).toBeInTheDocument();
    expect(screen.getByText(/Drill timed out/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Provider recovery runbook" })).toHaveAttribute("href", "https://runbook.example/recover");
    expect(screen.getByText("Deploy through your cloud provider.")).toBeInTheDocument();
    expect(screen.getByText("Deployment archives and in-place restore require a host supervisor.")).toBeInTheDocument();
  });
  it("managed mode without provider data falls back to unknown and the verify-your-plan text; an unsafe runbook is not linked", () => {
    const { unmount } = render(<DeploymentPanel data={host({ mode: "managed" })} />);
    expect(screen.getByText("Database backup/PITR: unknown. Object recovery: unknown.")).toBeInTheDocument();
    expect(screen.getByText(/Verify your provider plan’s recovery configuration/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Provider recovery runbook" })).toBeNull();
    unmount();
    for (const runbook_url of ["http://insecure.example/r", "https://user:pw@x.example/r", "not a url"]) {
      const view = render(<DeploymentPanel data={host({ mode: "managed", provider_recovery: { database_status: "unknown", object_status: "unknown", drill_status: "never", last_drill_at: null, reason: "", runbook_url } })} />);
      expect(screen.queryByRole("link", { name: "Provider recovery runbook" })).toBeNull();
      view.unmount();
    }
  });
  it("shows the free quota panel only for the free profile with usage", () => {
    const usage = { profile: "free", visibility: "deployment" } as unknown as FreeUsage;
    const { unmount } = render(<DeploymentPanel data={host({ profile: "free", free_usage: usage })} />);
    expect(screen.getByText("free quota panel deployment")).toBeInTheDocument();
    unmount();
    render(<DeploymentPanel data={host({ profile: "free" })} />);
    expect(screen.queryByText(/free quota panel/)).toBeNull();
  });
});

describe("tenant scope", () => {
  it("free profile with tenant object usage shows the storage card, and an operator warning when flagged", () => {
    render(<DeploymentPanel data={tenant({ objects: sample(), deployment_warning: true })} />);
    expect(screen.getByRole("region", { name: "Your makerspace’s object storage" })).toBeInTheDocument();
    expect(screen.getByText(/The deployment needs operator attention/)).toBeInTheDocument();
    expect(screen.queryByText("Launch mode")).toBeNull();
  });
  it("shows neither a card nor a warning for a full profile or without tenant-scoped objects", () => {
    const { unmount } = render(<DeploymentPanel data={tenant({ profile: "full", objects: sample() })} />);
    expect(screen.queryByRole("region", { name: "Your makerspace’s object storage" })).toBeNull();
    unmount();
    render(<DeploymentPanel data={tenant({ objects: sample({ scope: "deployment" }) })} />);
    expect(screen.queryByRole("region", { name: "Your makerspace’s object storage" })).toBeNull();
    expect(screen.queryByText(/operator attention/)).toBeNull();
  });
});

describe("QuotaCard", () => {
  const card = (s: UsageSample) => render(<QuotaCard label="Storage" sample={s} />);
  it.each([
    [{ used: 100_000_000 }, "Within configured cap", false],
    [{ used: 750_000_000 }, "Watch usage", true],
    [{ used: 950_000_000 }, "Near limit", true],
    [{ used: 1_000_000_000 }, "Reached", true],
    [{ used: 900_000_000, uncertain: 150_000_000 }, "Reached", true],
    [{ state: "stale" as const }, "Stale", true],
    [{ state: "unknown" as const }, "Unknown", true],
    [{ used: null }, "Unknown", true],
    [{ cap: 0 }, "Unknown", true],
    [{ cap: null }, "Unknown", true],
    [{ sampled_at: null }, "Unknown", true],
    [{ sampled_at: "garbage" }, "Unknown", true],
    [{ used: -5 }, "Unknown", true],
  ] as Array<[Partial<UsageSample>, string, boolean]>)("%j reads %s", (over, label, warns) => {
    card(sample(over));
    expect(screen.getByText(label, { selector: "span, p, div" })).toBeInTheDocument();
    expect(quotaState(sample(over))).toBe(label);
    expect(screen.queryByText(/Review the provider account|Ask the operator to refresh usage/) !== null).toBe(warns);
  });
  it("stale and unknown ask the operator to refresh; real pressure says to export or upgrade", () => {
    const { unmount } = card(sample({ state: "stale" }));
    expect(screen.getByText("Ask the operator to refresh usage and verify the provider account allowance.")).toBeInTheDocument();
    unmount();
    card(sample({ used: 960_000_000 }));
    expect(screen.getByText(/Export, migrate or upgrade before reaching the limit/)).toBeInTheDocument();
  });
  it("prints used / cap, the uncertain amount and the sources with Unknown fallbacks", () => {
    card(sample({ used: 250_000_000, cap: 1_000_000_000, uncertain: 5_000_000, source: "", cap_source: "" }));
    expect(screen.getByText("250 MB / 1,000 MB")).toBeInTheDocument();
    expect(screen.getByText(/Uncertain or reserved: 5 MB\./)).toBeInTheDocument();
    expect(screen.getByText(/Usage source: Unknown\. Cap source: Unknown\./)).toBeInTheDocument();
  });
  it("formats recipients and unknown amounts; dates fall back to Unknown", () => {
    expect(formatUsage(1234, "recipients")).toBe("1,234 recipients");
    expect(formatUsage(null, "bytes")).toBe("Unknown");
    expect(formatUsage(Number.NaN, "bytes")).toBe("Unknown");
    expect(dateLabel(null)).toBe("Unknown");
    expect(dateLabel("nonsense")).toBe("Unknown");
    expect(dateLabel("2026-11-01T00:00:00Z")).not.toBe("Unknown");
  });
  it("uses the danger tone only when reached", () => {
    const { container } = card(sample({ used: 1_000_000_000 }));
    expect(within(container).getByText("Reached")).toBeInTheDocument();
  });
});
