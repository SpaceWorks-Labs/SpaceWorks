import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackupRestorePanel } from "./BackupRestorePanel";
import { RecoveryQuarantinePanel } from "./RecoveryQuarantinePanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
vi.mock("../../components/SpaceWorksLogo", async () => ({
  ...await vi.importActual<typeof import("../../components/SpaceWorksLogo")>("../../components/SpaceWorksLogo"),
  SpaceWorksBadge: () => <span />,
}));
vi.mock("../deployment/DeploymentNotices", () => ({ DeploymentNotices: () => <p>Managed deployment recovery</p> }));

function withQueryClient(element: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {element}
    </QueryClientProvider>,
  );
}

// The panel asks the platform dashboard for the deployment mode first; host controls and every
// deployment-backup query wait for mode "host" (cloud lane). Managed deployments get recovery notices only.
const DASHBOARD = "/admin/platform/dashboard";
function deploymentMode(mode: "host" | "managed") {
  return { deployment: { mode, profile: "full", scanner: "none", media_validation_available: true } };
}
/** Wraps a per-test route table so the dashboard answers with the deployment mode before anything else. */
function routes(mode: "host" | "managed", rest: (path: string, options?: RequestInit) => Promise<unknown>) {
  staffRequest.mockImplementation((path: string, options?: RequestInit) =>
    path === DASHBOARD ? Promise.resolve(deploymentMode(mode)) : rest(path, options));
}

beforeEach(() => { staffRequest.mockReset(); });

describe("BackupRestorePanel", () => {
  it("states the purge boundary and shows an all-table restore report", async () => {
    const deadline = new Date(Date.now() + 60_000).toISOString();
    routes("host", (path: string) => {
      if (path === "/admin/platform/backup-settings") return Promise.resolve({ automatic_backups_enabled: true, retention_days: 30, last_scheduled_at: null, last_success_at: null, last_error: "" });
      if (path === "/admin/platform/restores") return Promise.resolve([{ id: "restore-1", stage: "quiesced" }]);
      if (path === "/admin/platform/restores/restore-1") return Promise.resolve({ id: "restore-1", archive: "archive-1", kind: "rollback_in_place", stage: "quiesced", decision: "pending", decision_deadline_at: deadline, error_detail: "", requested_at: deadline, restore_diff: { tables_compared: 204, tables_changed: 1, tables: [{ table: "accounts_user", security_relevant: true, noisy: false, live: { row_count: 8 }, archive: { row_count: 9 }, row_diff: { removed_count: 1 } }] } });
      return Promise.resolve([]);
    });

    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin />);

    expect(await screen.findAllByText(/outside makerspace purge guarantees/i)).toHaveLength(1);
    expect(await screen.findByText(/204 tables compared; 1 differ/i)).toBeVisible();
    expect(screen.getByText(/accounts_user/)).toBeVisible();
    expect(screen.getByText(/security-relevant/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Abort safely" })).toBeEnabled();
  });

  it("persists operator retention settings", async () => {
    routes("host", (path: string, options?: RequestInit) => {
      if (path === "/admin/platform/backup-settings" && options?.method === "PATCH") return Promise.resolve({ automatic_backups_enabled: false, retention_days: 45, last_scheduled_at: null, last_success_at: null, last_error: "" });
      if (path === "/admin/platform/backup-settings") return Promise.resolve({ automatic_backups_enabled: false, retention_days: 30, last_scheduled_at: null, last_success_at: null, last_error: "" });
      return Promise.resolve([]);
    });
    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin />);
    const input = await screen.findByRole("spinbutton", { name: /archive retention/i });
    fireEvent.change(input, { target: { value: "45" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/platform/backup-settings",
      { method: "PATCH", body: JSON.stringify({ retention_days: 45 }) },
    ));
  });


  it("requires the deployment name before it sends a restore request", async () => {
    routes("host", (path: string) => {
      if (path === "/admin/platform/backups") return Promise.resolve([{ id: "archive-1", scope: "deployment", status: "available", created_at: "2026-10-10T00:00:00Z", size_bytes: 1024, failure_detail: "" }]);
      if (path === "/admin/platform/backup-settings") return Promise.resolve({ automatic_backups_enabled: false, retention_days: 30, last_success_at: null, last_error: "" });
      return Promise.resolve([]);
    });
    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin />);
    const open = await screen.findByRole("button", { name: "Restore from a backup…" });
    await waitFor(() => expect(open).toBeEnabled()); fireEvent.click(open);
    const dialog = screen.getByRole("dialog");
    const start = within(dialog).getByRole("button", { name: "Start restore…" });
    expect(start).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Type deployment to confirm"), { target: { value: "wrong" } });
    expect(start).toBeDisabled();
    expect(staffRequest.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
    fireEvent.change(within(dialog).getByLabelText("Type deployment to confirm"), { target: { value: "deployment" } });
    fireEvent.click(start);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/restores", { method: "POST", body: JSON.stringify({ archive: "archive-1", kind: "rollback_in_place" }) }));
  });

  it("never queries or offers makerspace archives to platform accounts", async () => {
    routes("host", () => Promise.resolve([]));
    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin />);
    expect(await screen.findByRole("button", { name: "Create full deployment archive" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Create makerspace archive" })).toBeNull();
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspace/7/backups");
  });

  it("shows a manager only the read-only last-backup line", async () => {
    staffRequest.mockImplementation((path: string) => path === "/admin/makerspace/7/backup-status"
      ? Promise.resolve({ last_backed_up_at: null, nightly_backups_enabled: true })
      : Promise.resolve([]));
    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin={false} />);
    expect(await screen.findByText("No backup yet")).toBeVisible();
    expect(screen.getByText(/use Data export/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Create makerspace archive" })).toBeNull();
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspace/7/backups");
  });

  // Merged from the cloud lane (cl-i): a managed deployment never reaches the host backup routes.
  it("suppresses managed host queries and destructive controls", async () => {
    routes("managed", () => Promise.resolve([]));
    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin />);
    expect(await screen.findByText("Managed deployment recovery")).toBeVisible();
    for (const path of ["/admin/platform/backups", "/admin/platform/restores", "/admin/platform/backup-settings"]) {
      expect(staffRequest).not.toHaveBeenCalledWith(path);
    }
    expect(screen.queryByRole("button", { name: "Create full deployment archive" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Restore from a backup/ })).toBeNull();
  });

  it("retains full host backup queries after its mode is established", async () => {
    routes("host", (path: string) => path === "/admin/platform/backup-settings"
      ? Promise.resolve({ automatic_backups_enabled: false, retention_days: 30, last_scheduled_at: null, last_success_at: null, last_error: "" })
      : Promise.resolve([]));
    withQueryClient(<BackupRestorePanel makerspaceId={7} isSuperadmin />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/backups"));
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/restores");
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/backup-settings");
  });
});

describe("RecoveryQuarantinePanel", () => {
  it("sends the exact displayed residual-risk acknowledgement", async () => {
    staffRequest.mockResolvedValue({ mode: "normal" });
    const risk = "Exact residual risk statement";
    withQueryClient(<RecoveryQuarantinePanel state={{ mode: "quarantined", quarantine_reason: "Disaster restore", quarantined_at: null, residual_risk: risk }} onAcknowledged={() => undefined} />);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Lift quarantine" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/recovery",
      { method: "POST", body: JSON.stringify({ acknowledgement: risk }) },
    ));
  });
});
