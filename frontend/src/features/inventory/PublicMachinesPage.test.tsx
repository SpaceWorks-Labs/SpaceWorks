import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { PublicMachinesPage } from "./PublicMachinesPage";
import { tenantPublicRequest } from "../../lib/api";

vi.mock("../../lib/api", () => ({ tenantPublicRequest: vi.fn(), StructuredApiError: class extends Error {} }));
vi.mock("../../lib/tenant", () => ({
  useTenant: () => ({ mode: "single", slug: "lab", bootstrap: {
    features: ["machines.public_detail"], makerspace: { name: "Lab" }, branding: {},
  } }),
  useTenantPath: () => () => "/m/lab",
}));
vi.mock("../../lib/useTenantBranding", () => ({ useTenantBranding: () => ({}) }));
vi.mock("./usePublicInventory", () => ({ useTenantBootstrap: () => ({}) }));

it("loads subsequent machine pages through the tenant transport", async () => {
  const request = vi.mocked(tenantPublicRequest);
  request.mockImplementation(async (_slug, path) => ({
    count: 25, next: path.includes("page=1") ? "https://untrusted.example/page2" : null, previous: null,
    results: [{ id: 1, name: path.includes("page=2") ? "Second page laser" : "First page laser",
      machine_type: { id: 4, name: "Laser", icon: "" }, status: "idle", image_url: null, usage_hours: "0.00",
      queue: path.includes("page=2")
        ? { length: 3, eta_minutes: 65, estimated_clear_at: "2026-10-18T11:05:00Z", calculated_at: "2026-10-18T10:00:00Z", confidence: "estimated", reasons: [] }
        : { length: 2, eta_minutes: null, estimated_clear_at: null, calculated_at: "2026-10-18T10:00:00Z", confidence: "unavailable", reasons: ["missing_estimate"] } }],
  }));
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PublicMachinesPage />
  </QueryClientProvider></MemoryRouter>);
  await screen.findByText("First page laser");
  // Unknown work never reads as zero: the server's unavailable summary stays unavailable.
  expect(screen.getByText("Clear time unavailable")).toBeInTheDocument();
  expect(screen.getByText("2 jobs in line")).toBeInTheDocument();
  expect(screen.queryByText(/processing hours/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await screen.findByText("Second page laser");
  expect(screen.getByText(/Estimated queue clears in about 1 h 5 min/)).toBeInTheDocument();
  expect(document.querySelector("time[datetime='2026-10-18T11:05:00Z']")).not.toBeNull();
  await waitFor(() => expect(request).toHaveBeenCalledWith("lab", "/public/lab/machines/details?page=2&page_size=24"));
  expect(request.mock.calls.every(call => call[1].startsWith("/public/lab/"))).toBe(true);
});

it("filters published machine kinds and training requirements without another fetch", async () => {
  const request = vi.mocked(tenantPublicRequest); request.mockReset();
  request.mockResolvedValue({ count: 2, next: null, previous: null, results: [
    { id: 1, name: "Laser cutter", machine_type: { id: 1, name: "Laser", icon: "" }, status: "idle", image_url: null, usage_hours: "2", training_required: true },
    { id: 2, name: "Drill press", machine_type: { id: 2, name: "Drill", icon: "" }, status: "idle", image_url: null, usage_hours: "4", training_required: false },
  ] });
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PublicMachinesPage /></QueryClientProvider></MemoryRouter>);
  await screen.findByText("Laser cutter");
  fireEvent.click(screen.getByRole("button", { name: "Training required" }));
  expect(screen.queryByText("Drill press")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Training required" }));
  fireEvent.click(screen.getByRole("button", { name: "Drill" }));
  expect(screen.getByText("Drill press")).toBeVisible();
  expect(screen.queryByText("Laser cutter")).toBeNull();
  expect(request).toHaveBeenCalledTimes(1);
});

it("titles the public machines page with the makerspace name", async () => {
  const request = vi.mocked(tenantPublicRequest); request.mockReset();
  request.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PublicMachinesPage /></QueryClientProvider></MemoryRouter>);
  await waitFor(() => expect(document.title).toBe("Machines · Lab"));
});
