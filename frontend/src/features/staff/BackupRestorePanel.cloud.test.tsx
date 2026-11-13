import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BackupRestorePanel } from "./BackupRestorePanel";
import { getPlatformDashboard } from "./platformMonitoringApi";
import { listDeploymentBackups, listRestores, getBackupSettings } from "./backupApi";
vi.mock("./platformMonitoringApi", () => ({ getPlatformDashboard: vi.fn() }));
vi.mock("./backupApi", async importOriginal => ({ ...await importOriginal<typeof import("./backupApi")>(),
  listDeploymentBackups: vi.fn().mockResolvedValue([]), listRestores: vi.fn().mockResolvedValue([]),
  getBackupSettings: vi.fn().mockResolvedValue({ automatic_backups_enabled: false, retention_days: 30 }) }));
vi.mock("../deployment/DeploymentNotices", () => ({ DeploymentNotices: () => <p>Managed deployment recovery</p> }));
vi.mock("./BackupScheduleSettings", () => ({ BackupScheduleSettings: () => <p>Host backup schedule</p> }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function mount(mode: "managed" | "host") {
  vi.mocked(getPlatformDashboard).mockResolvedValue({ deployment: { mode, profile: "full", scanner: "none", media_validation_available: true } } as Awaited<ReturnType<typeof getPlatformDashboard>>);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><BackupRestorePanel makerspaceId={1} isSuperadmin /></QueryClientProvider>);
}
it("suppresses managed host queries and destructive controls", async () => {
  mount("managed");
  expect(await screen.findByText("Managed deployment recovery")).toBeTruthy();
  expect(listDeploymentBackups).not.toHaveBeenCalled();
  expect(listRestores).not.toHaveBeenCalled();
  expect(getBackupSettings).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Create full deployment archive" })).toBeNull();
});
it("retains full host backup queries after its mode is established", async () => {
  mount("host");
  await waitFor(() => expect(listDeploymentBackups).toHaveBeenCalled());
  expect(listRestores).toHaveBeenCalled();
  expect(getBackupSettings).toHaveBeenCalled();
});
