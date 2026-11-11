import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { SelfhostMovesSection } from "./SelfhostMovesSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const base = { makerspace: 1, note: "", requested_at: "2026-11-01T10:00:00Z", decided_at: null, decision_note: "",
  recipient_fingerprint: "", exported_at: null, artifact_sha256: "", failure_code: "", has_file: false };
const moves = [
  { ...base, id: "a1", makerspace_name: "North Lab", status: "requested", status_label: "Requested" },
  { ...base, id: "b2", makerspace_name: "South Lab", status: "approved", status_label: "Approved" },
  { ...base, id: "c3", makerspace_name: "East Lab", status: "exported", status_label: "Exported", has_file: true },
];
const AGE = "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p";

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><SelfhostMovesSection /></QueryClientProvider>);
}

describe("SelfhostMovesSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (_path, init) => (init?.method ? moves[1] : { count: 3, next: null, previous: null, results: moves }) as never);
  });

  it("keeps visible retry and delete actions in their accessible names", async () => {
    const failed = { ...base, id: "d4", makerspace_name: "West Lab", status: "failed", status_label: "Failed", has_file: true };
    request.mockResolvedValue({ count: 1, next: null, previous: null, results: [failed] } as never);
    renderSection();
    expect(await screen.findByText("Export again…", { selector: "button", exact: true })).toHaveAccessibleName(/^Export again… West Lab$/);
    expect(screen.getByText("Delete file…", { selector: "button", exact: true })).toHaveAccessibleName(/^Delete file… West Lab$/);
  });

  it("keeps the visible preparing action named while its one-use link loads", async () => {
    request.mockImplementation(async (_path, init) => (init?.method ? new Promise(() => {}) : { count: 3, next: null, previous: null, results: moves }) as never);
    renderSection();
    fireEvent.click(await screen.findByText("Download", { selector: "button", exact: true }));
    const preparing = await screen.findByText("Preparing…", { selector: "button", exact: true });
    expect(preparing).toHaveAccessibleName(/^Preparing… East Lab$/);
    expect(preparing).toBeDisabled();
    expect(request).toHaveBeenCalledWith("/admin/platform/selfhost-moves/c3/download-url", { method: "POST", body: "{}" }, "platform");
  });

  it("offers the right controls for each status", async () => {
    renderSection();
    expect(await screen.findByRole("button", { name: "Approve the move of North Lab" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline the move of North Lab" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export… South Lab" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download East Lab" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete file… East Lab" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export… North Lab" })).not.toBeInTheDocument();
  });

  it("exports only to an age public key", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: "Export… South Lab" }));
    const start = screen.getByRole("button", { name: "Start export" });
    fireEvent.change(screen.getByRole("textbox", { name: "The new server's encryption key (starts with age1)" }), { target: { value: "ssh-ed25519 AAAA" } });
    expect(start).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "The new server's encryption key (starts with age1)" }), { target: { value: AGE } });
    fireEvent.click(start);
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/selfhost-moves/b2/export",
      { method: "POST", body: JSON.stringify({ recipient: AGE }) }, "platform"));
  });

  it("filters by status", async () => {
    renderSection();
    await screen.findByText("North Lab");
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "exported" } });
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/selfhost-moves?page=1&status=exported", {}, "platform"));
  });
});
