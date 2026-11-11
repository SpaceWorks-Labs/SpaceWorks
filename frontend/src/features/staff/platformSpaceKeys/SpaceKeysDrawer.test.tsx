import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import type { HealthCard } from "../platformSpaces/spacesApi";
import { CapabilityPurgeDrawer } from "./CapabilityPurgeDrawer";
import { SpaceKeysDrawer } from "./SpaceKeysDrawer";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);
const card = { id: 7, name: "North Lab", slug: "north-lab" } as HealthCard;
const job = { id: 1, kind: "rotation", status: "running", from_version: 1, to_version: 2, rows_done: 40, rows_skipped: 0,
  retained_versions: [], error_code: "", started_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:01:00Z", completed_at: null };
const keys = { active_dek_version: 2, dek_versions: [], search_key_version: null, publishable_key_rotated_at: null,
  previous_publishable_key_valid_until: null, jobs: [job], running: job, pii_encryption_enabled: true, rls_mode: "enforce",
  stale_archives: [{ id: "11111111-2222", completed_at: "2026-10-01T10:00:00Z", size_bytes: 10, reencryptable: true, job: null }] };
const plans = [{ key: "machines.tobuy", summary: "Machine consumables to buy", switched_on: false, counts: { to_buy_items: 3 } },
  { key: "inventory.tobuy", summary: "Hardware to buy", switched_on: true, counts: { to_buy_items: 1 } }];

function renderWith(node: React.ReactNode) {
  request.mockImplementation(async (path, init) => {
    if (path.endsWith("/keys")) return keys as never;
    if (path.endsWith("/capability-purge")) return (init?.method === "POST" ? { key: "machines.tobuy", counts: { to_buy_items: 3 } } : plans) as never;
    return { archive_id: "11111111-2222", job: { action: "purge", state: "queued", error_code: "", updated_at: "" } } as never;
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("SpaceKeysDrawer", () => {
  beforeEach(() => { request.mockReset(); });

  it("shows job progress and holds rotations while a job runs", async () => {
    renderWith(<SpaceKeysDrawer card={card} onClose={() => {}} />);
    expect(await screen.findByText(/40 records done/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rotate the data key…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rotate the browser key…" })).toBeEnabled();
  });

  it("purges an archive only after the slug is typed back", async () => {
    renderWith(<SpaceKeysDrawer card={card} onClose={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Purge…" }));
    const dialog = await screen.findByRole("dialog", { name: "Purge this archive" });
    const confirm = within(dialog).getByRole("button", { name: "Purge for good" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Type north-lab to confirm"), { target: { value: "north-lab" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/spaces/7/keys/archives/11111111-2222",
      { method: "POST", body: JSON.stringify({ action: "purge", confirm_slug: "north-lab" }) }, "platform"));
  });
});

describe("CapabilityPurgeDrawer", () => {
  beforeEach(() => { request.mockReset(); });

  it("previews the rows and needs the capability key typed back", async () => {
    renderWith(<CapabilityPurgeDrawer card={card} onClose={() => {}} />);
    expect(await screen.findByText("Switched on")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Purge machines.tobuy data" }));
    const dialog = await screen.findByRole("dialog", { name: "Purge machines.tobuy data" });
    expect(within(dialog).getByText(/To-buy items: 3/)).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Type machines.tobuy to confirm"), { target: { value: "machines.tobuy" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Purge for good" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/spaces/7/capability-purge",
      { method: "POST", body: JSON.stringify({ key: "machines.tobuy", confirm: "machines.tobuy" }) }, "platform"));
  });
});
