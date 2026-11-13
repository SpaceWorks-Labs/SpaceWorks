import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AreaAllowances } from "./AreaAllowances";
import type { AllowanceRow } from "./allowancesApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const mount = (ui: React.ReactElement) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}>{ui}</QueryClientProvider>);

const row = (overrides: Partial<AllowanceRow>): AllowanceRow => ({
  key: "products", label: "products", unit: "count", limit: 10, used: 2, remaining: 8, percent: 20, level: "ok",
  areas: ["inventory"], ...overrides,
});

beforeEach(() => { staffRequest.mockReset(); });

describe("remaining allowance per role (#234 addendum 3a)", () => {
  it("shows only the tab's area, with a warning at 80% and a stop at 100%", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, areas: ["inventory", "machines"], rows: [
      row({ used: 8, remaining: 2, percent: 80, level: "warning" }),
      row({ key: "storage", label: "storage", unit: "bytes", limit: 1048576, used: 1048576, remaining: 0, percent: 100, level: "limit" }),
      row({ key: "machines", label: "machines", areas: ["machines"] }),
    ] });
    mount(<AreaAllowances makerspaceId={7} tab="inventory" />);
    expect(await screen.findByText("Limits for this area")).toBeVisible();
    expect(screen.getByText(/Products: 80% used/)).toBeVisible();
    expect(screen.getByText(/Storage: this space has reached its limit of 1 MB/)).toBeVisible();
    expect(screen.queryByText("Machines")).not.toBeInTheDocument();
  });

  it("lists every managed area on the dashboard", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, areas: ["inventory", "machines"], rows: [row({}), row({ key: "machines", label: "machines", areas: ["machines"] })] });
    mount(<AreaAllowances makerspaceId={7} tab="dashboard" />);
    expect(await screen.findByText("Plan & usage")).toBeVisible();
    expect(screen.getByText("Machines")).toBeVisible();
    expect(screen.getAllByText("2 of 10 used · 8 left")).toHaveLength(2);
  });

  it("renders nothing when nothing is limited", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, areas: ["inventory"], rows: [] });
    const { container } = mount(<AreaAllowances makerspaceId={7} tab="inventory" />);
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });
  it("shows the staff seat limit on Staff and the storage row on Shop (A29)", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, areas: ["shop", "staff"], rows: [
      row({ key: "staff", label: "staff members", areas: ["staff"] }),
      row({ key: "storage", label: "storage", areas: ["inventory", "shop"] }),
    ] });
    const users = mount(<AreaAllowances makerspaceId={7} tab="users" />);
    expect(await screen.findByText("Staff members")).toBeVisible();
    expect(screen.queryByText("Storage")).not.toBeInTheDocument();
    users.unmount();
    mount(<AreaAllowances makerspaceId={7} tab="shop" />);
    expect(await screen.findByText("Storage")).toBeVisible();
    expect(screen.queryByText("Staff members")).not.toBeInTheDocument();
  });
});
