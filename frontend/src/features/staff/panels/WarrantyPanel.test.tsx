import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WarrantyPanel } from "./WarrantyPanel";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));
vi.mock("../WarrantySection", () => ({ WarrantySection: ({ hostKind, hostId }: { hostKind: string; hostId: number }) => <div>section {hostKind} {hostId}</div> }));

const row = (over = {}) => ({ host_kind: "machine", host_id: 1, host_label: "Laser cutter", serial_number: "SN-1", vendor_name: "Acme",
  purchased_on: "2025-01-02", warranty_expires_on: null, status: "active", document_count: 2, ...over });
const rows = [row(), row({ host_kind: "asset", host_id: 2, host_label: "Drill", vendor_name: null }), row({ host_kind: "printer", host_id: 3, host_label: "Prusa" })];

function setup(canEditInventory = true, path = "/admin/warranties") {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><WarrantyPanel makerspace={{ id: 7, slug: "forge", name: "Forge" } as Makerspace} canEditInventory={canEditInventory} /></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { request.mockReset(); });

describe("WarrantyPanel (IN-14)", () => {
  it("lists warranty rows from the paged endpoint with vendor fallback and doc counts", async () => {
    request.mockResolvedValue({ count: 3, next: null, previous: null, results: rows });
    setup();
    expect(await screen.findByText("Laser cutter")).toBeInTheDocument();
    expect(request.mock.calls[0][0]).toBe("/admin/makerspace/7/warranties?page=1&page_size=50");
    expect(screen.getByText(/No vendor recorded/)).toBeInTheDocument();
    expect(screen.getAllByText("2 docs").length).toBe(3);
  });

  it("offers Manage on machines, only to inventory editors on assets, and never on printers", async () => {
    request.mockResolvedValue({ count: 3, next: null, previous: null, results: rows });
    setup(false);
    await screen.findByText("Laser cutter");
    expect(screen.getAllByRole("button", { name: "Manage" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Manage" }));
    expect(await screen.findByText("section machine 1")).toBeInTheDocument();
  });

  it("lets an inventory editor manage the asset row too", async () => {
    request.mockResolvedValue({ count: 3, next: null, previous: null, results: rows });
    setup(true);
    await screen.findByText("Laser cutter");
    expect(screen.getAllByRole("button", { name: "Manage" })).toHaveLength(2);
  });

  it("sends the status, missing-docs and expires-before filters to the server", async () => {
    request.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    setup(true, "/admin/warranties?status=expired&missing_docs=true&expires_before=2026-12-31");
    await waitFor(() => expect(request).toHaveBeenCalled());
    const url = new URL(request.mock.calls[0][0], "http://x");
    expect(url.searchParams.get("status")).toBe("expired");
    expect(url.searchParams.get("missing_docs")).toBe("true");
    expect(url.searchParams.get("expires_before")).toBe("2026-12-31");
    expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
  });

  it("shows the empty state when nothing is recorded", async () => {
    request.mockResolvedValueOnce({ count: 0, next: null, previous: null, results: [] });
    setup();
    expect(await screen.findByText(/No warranties recorded yet/)).toBeInTheDocument();
  });

  it("shows an error state when the warranties cannot load", async () => {
    request.mockRejectedValue(new Error("boom"));
    setup();
    expect(await screen.findByText(/Couldn.t load warranties/)).toBeInTheDocument();
  });
});
