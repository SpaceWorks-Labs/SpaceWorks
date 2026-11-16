import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { StocktakePanel } from "./StocktakeSessionPanel";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request, downloadStaffFile: vi.fn() }));
const space = { id: 7, slug: "forge", name: "Forge", enabled_features: [], enabled_modules: [] } as unknown as Makerspace;
const row = (id: number, status: string, extra = {}) => ({ id, status, notes: `Count ${id}`, container: null, approval_required: true, ...extra });

function setup(props: { isSuperadmin?: boolean; canConfigure?: boolean } = {}, sessions: unknown[] = []) {
  request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (init?.method === "POST") return {};
    if (String(path).includes("/stocktakes")) return { count: sessions.length, results: sessions };
    return { count: 0, results: [] };
  });
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StocktakePanel makerspace={space} {...props} /></QueryClientProvider></MemoryRouter>);
}
beforeEach(() => request.mockReset());

it("shows the empty state with a Start count action when there are no sessions", async () => {
  setup();
  expect(await screen.findByText(/No counts yet/)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Start count" }).length).toBeGreaterThan(0);
});

it("offers Continue on a counting session and never Approve or Apply to a plain staff member", async () => {
  setup({}, [row(1, "counting"), row(2, "completed"), row(3, "approved")]);
  expect(await screen.findByRole("button", { name: "Continue" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Open count" })).toHaveLength(2);
  expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Apply adjustments" })).not.toBeInTheDocument();
});

it("lets a superadmin approve a completed count and asks for confirmation before applying an approved one", async () => {
  setup({ isSuperadmin: true }, [row(2, "completed"), row(3, "approved")]);
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/stocktakes/2/approve", expect.objectContaining({ method: "POST" })));
  fireEvent.click(screen.getByRole("button", { name: "Apply adjustments" }));
  // Applying changes real inventory numbers: nothing is posted until the dialog is confirmed.
  expect(request).not.toHaveBeenCalledWith("/admin/stocktakes/3/apply-adjustments", expect.anything());
  expect(await screen.findByText("Inventory numbers will change to match this approved count.")).toBeInTheDocument();
});

it("shows a retryable error when the session list fails to load", async () => {
  request.mockImplementation(async (path: string) => { if (String(path).includes("/stocktakes")) throw new Error("boom"); return { count: 0, results: [] }; });
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StocktakePanel makerspace={space} /></QueryClientProvider></MemoryRouter>);
  expect(await screen.findByText("Couldn't load stocktake sessions. Try again.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
});
