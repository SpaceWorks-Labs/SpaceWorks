import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackupRestorePanel } from "./BackupRestorePanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
vi.mock("../deployment/DeploymentNotices", () => ({ DeploymentNotices: () => <p>Managed</p> }));

const SCHEDULE = {
  automatic_backups_enabled: true, platform_nightly: "Every night at 02:00", spaces_nightly: "Nightly",
  spaces_per_tick: 2, daily_keep_days: 7, weekly_keep_weeks: 4, on_demand_keep_days: 30,
  server_restore_key_configured: true, last_platform_success_at: null,
  spaces: [{ makerspace_id: 7, slug: "lab", name: "Lab", last_nightly_at: null, last_backup_at: null }],
};
const POINT = { id: "a-1", scope: "makerspace", makerspace: 7, status: "available", manifest: {}, size_bytes: 2048,
  age_encrypted: true, failure_detail: "", expires_at: null, created_at: "2026-10-29T01:00:00Z",
  completed_at: "2026-10-29T01:05:00Z", purge_warning: "", trigger: "nightly", format: "tenant_slice_v1", restorable_in_app: true };
const PREVIEW = { snapshot_at: "2026-10-29T01:00:00Z", models: [{ label: "hardware_requests.HardwareRequest", live: 3, archived: 2, removed: 1, added: 0 }],
  totals: { archived_rows: 2, live_rows: 3, removed_rows: 1, added_rows: 0 }, memberships: { removed: 0, restored: 0 },
  accounts: { referenced: 1, reattributed: 0, erased_since: 0 },
  money_after_restore_point: [{ model: "payments.Payment", pk: "9", created_at: "2026-10-29T02:00:00Z", amount: "5.00", currency: "usd", status: "pending" }],
  evidence_after_restore_point: 1, objects: { count: 1, bytes: 10 }, inbound_relinked: 0, blocking: [], blocking_count: 0, blocked: false };
const RESTORE = { id: "r-1", makerspace: 7, makerspace_slug: "lab", makerspace_name: "Lab", archive: "a-1", source: "space_archive",
  safety_archive: null, stage: "preview_ready", snapshot_at: PREVIEW.snapshot_at, preview: PREVIEW, progress: {}, report: {},
  error_code: "", error_detail: "", blocked: false, created_at: "2026-10-30T00:00:00Z", finished_at: null };

function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <BackupRestorePanel makerspaceId={7} isSuperadmin />
  </QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string, options?: RequestInit) => {
    if (options?.method === "POST" && path === "/admin/makerspace/7/restores") return Promise.resolve(RESTORE);
    if (options?.method === "POST" && path === "/admin/makerspace/7/backups") return Promise.resolve(POINT);
    if (path === "/admin/platform/dashboard") return Promise.resolve({ deployment: { mode: "managed", profile: "full" } });
    if (path === "/admin/platform/backup-schedule") return Promise.resolve(SCHEDULE);
    if (path === "/admin/makerspace/7/backups") return Promise.resolve([POINT]);
    if (path === "/admin/makerspace/7/restores") return Promise.resolve([]);
    if (path === "/admin/space-restores/r-1") return Promise.resolve(RESTORE);
    if (path === "/admin/space-restores/r-1/confirm") return Promise.resolve({ ...RESTORE, stage: "applying", progress: { percent: 30, step: "safety_backup" } });
    return Promise.resolve(RESTORE);
  });
});

describe("one-space backup and restore", () => {
  it("previews, then confirms only with the typed slug", async () => {
    mount();
    await screen.findByRole("option", { name: "One space: Lab" });
    fireEvent.change(screen.getByLabelText(/scope/i), { target: { value: "7" } });
    fireEvent.click(await screen.findByRole("button", { name: "Restore…" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/restores",
      { method: "POST", body: JSON.stringify({ archive: "a-1" }) }));
    expect(await screen.findByText(/1 payment record\(s\)/)).toBeVisible();
    const restore = screen.getByRole("button", { name: "Restore this space" });
    expect(restore).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/to confirm/i), { target: { value: "lab" } });
    fireEvent.click(screen.getByRole("button", { name: "Restore this space" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/space-restores/r-1/confirm",
      { method: "POST", body: JSON.stringify({ confirm_slug: "lab" }) }));
  });

  it("starts a one-space backup now", async () => {
    mount();
    await screen.findByRole("option", { name: "One space: Lab" });
    fireEvent.change(screen.getByLabelText(/scope/i), { target: { value: "7" } });
    fireEvent.click(await screen.findByRole("button", { name: "Back up now" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/backups", { method: "POST", body: "{}" }));
  });

  it("keeps the space backup controls from a Space Manager", async () => {
    render(<QueryClientProvider client={new QueryClient()}><BackupRestorePanel makerspaceId={7} isSuperadmin={false} /></QueryClientProvider>);
    expect(await screen.findByText(/For your own copy/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Back up now" })).toBeNull();
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/platform/backup-schedule");
  });
});
