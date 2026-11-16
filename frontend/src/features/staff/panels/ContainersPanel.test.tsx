import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContainersPanel } from "./ContainersPanel";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));
vi.mock("./ContainerDetail", () => ({ ContainerDetail: (p: { container: { label: string }; warrantyEnabled: boolean; kitEnabled: boolean; canEditInventory: boolean }) =>
  <div>detail {p.container.label} warranty:{String(p.warrantyEnabled)} kit:{String(p.kitEnabled)} edit:{String(p.canEditInventory)}</div> }));
vi.mock("./ContainerCreateModal", () => ({ ContainerCreateModal: ({ open }: { open: boolean }) => open ? <div>create modal</div> : null }));

const containers = [
  { id: 1, code: "BX-1", label: "Soldering box", location: "Shelf A", is_active: true },
  { id: 2, code: "BX-2", label: "Old bin", location: "Cellar", is_active: false },
];
function setup(path = "/admin/containers", features: string[] = []) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><ContainersPanel makerspace={{ id: 7, slug: "forge", name: "Forge", enabled_features: features } as unknown as Makerspace} canEditInventory /></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { request.mockReset(); });

describe("ContainersPanel (IN-14)", () => {
  it("lists containers from the scoped endpoint", async () => {
    request.mockResolvedValue({ results: containers });
    setup();
    expect(await screen.findByText("Soldering box")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/makerspace/7/containers?page_size=1000");
    expect(screen.getByText("Old bin")).toBeInTheDocument();
    expect(screen.getByText("BX-1 · Shelf A")).toBeInTheDocument();
  });

  it("filters by the inactive tab", async () => {
    request.mockResolvedValue({ results: containers });
    setup("/admin/containers?view=inactive");
    expect(await screen.findByText("Old bin")).toBeInTheDocument();
    expect(screen.queryByText("Soldering box")).toBeNull();
  });

  it("filters by search text and shows the filtered-empty message", async () => {
    request.mockResolvedValue({ results: containers });
    setup("/admin/containers?q=zzz");
    expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
  });

  it("shows the empty state with a create action, which opens the create modal", async () => {
    request.mockResolvedValue({ results: [] });
    setup();
    expect(await screen.findByText(/No containers yet/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /New container/ })[0]);
    expect(await screen.findByText("create modal")).toBeInTheDocument();
  });

  it("opens the selected container with module flags derived from enabled features", async () => {
    request.mockResolvedValue({ results: containers });
    setup("/admin/containers?container=1", ["inventory.warranty"]);
    expect(await screen.findByText(/detail Soldering box warranty:true kit:false edit:true/)).toBeInTheDocument();
  });

  it("shows an error state when containers cannot load", async () => {
    request.mockRejectedValue(new Error("boom"));
    setup();
    expect(await screen.findByText(/Couldn.t load containers/)).toBeInTheDocument();
  });
});
