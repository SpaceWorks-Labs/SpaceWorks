import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { RestoreDrillsSection } from "./RestoreDrillsSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const overview = (configured: boolean) => ({ configured, key_rotation: "On the server: manage.py backup_keys.",
  settings: { restore_drill_interval_days: 30, archive_ready_notice_enabled: false } });
const reports = [
  { id: 1, makerspace_id: 2, makerspace_name: "North Lab", started_at: "2026-11-01T10:00:00Z", finished_at: "2026-11-01T10:05:00Z",
    outcome: "passed", error_code: "", checks: { row_total: 120, objects_verified: 8 } },
  { id: 2, makerspace_id: 9, makerspace_name: null, started_at: "2026-11-02T10:00:00Z", finished_at: null,
    outcome: "failed", error_code: "archive_unreadable", checks: {} },
];

function renderSection(configured: boolean) {
  request.mockImplementation(async (path, init) => {
    if (path === "/admin/platform/restore-drills/settings") return (init?.method === "PATCH" ? overview(configured).settings : overview(configured)) as never;
    if (path.startsWith("/admin/platform/space-health")) return page([]) as never;
    return page(reports) as never;
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><RestoreDrillsSection /></QueryClientProvider>);
}

describe("RestoreDrillsSection", () => {
  beforeEach(() => { request.mockReset(); });

  it("shows reports, the server-only note and blocks running drills until configured", async () => {
    renderSection(false);
    expect(await screen.findByText(/not set up on this server/)).toBeInTheDocument();
    expect(screen.getByText("On the server: manage.py backup_keys.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run a drill now" })).toBeDisabled();
    expect(await screen.findByText("North Lab")).toBeInTheDocument();
    expect(screen.getByText("Passed")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Space #9 (deleted)")).toBeInTheDocument();
  });

  it("saves the drill interval", async () => {
    renderSection(true);
    const days = await screen.findByRole("spinbutton", { name: "Days between drills of each space" });
    fireEvent.change(days, { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/restore-drills/settings", { method: "PATCH",
      body: JSON.stringify({ restore_drill_interval_days: 0, archive_ready_notice_enabled: false }) }, "platform"));
  });
});
