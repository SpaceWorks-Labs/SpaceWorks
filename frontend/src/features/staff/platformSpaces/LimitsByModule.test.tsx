import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SpaceLimitsUsage } from "../hostingPlan/SpaceLimitsUsage";
import { LimitDefaultsSection } from "./LimitDefaultsSection";
import { SpaceLimitsSection } from "./SpaceLimitsSection";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const GROUPS = [{ key: "inventory", label: "Inventory" }, { key: "devices", label: "Connected devices" }, { key: "shop", label: "Shop" }];
const DEFAULTS = {
  groups: GROUPS,
  rows: [
    { key: "products", label: "products", unit: "count", module: "public_inventory", group: "inventory", default: 200 },
    { key: "adapter_media_bytes", label: "storage", unit: "bytes", module: "devices", group: "devices", default: null },
    { key: "shop_products", label: "shop products", unit: "count", module: "shop", group: "shop", default: null },
  ],
};
const SPACE = {
  custom_domain: false, hosted: false, groups: GROUPS, areas: [{ key: "people", label: "People" }],
  rows: [{ key: "products", label: "products", unit: "count", area: "inventory", group: "inventory", module: "public_inventory",
    effective: 200, source: "default", override: null, has_override: false, used: 170, suggested: null, platform_default: 200 }],
  quota_rows: [{ key: "adapter_media_bytes", label: "x", unit: "bytes", area: "machines", group: "devices", module: "devices",
    limit: null, used: 0, percent: null, level: "ok", platform_default: 5 * 1024 ** 3 }],
  platform_rows: [],
};
const mount = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
const puts = () => staffRequest.mock.calls.filter(([, init]) => init?.method === "PUT").map(([path, init]) => [path, JSON.parse(init.body)]);

beforeEach(() => { staffRequest.mockReset(); });

describe("platform default limits (decision 328a)", () => {
  beforeEach(() => { staffRequest.mockResolvedValue(DEFAULTS); });

  it("lists every key under its module heading, Unlimited where no default is set", async () => {
    mount(<LimitDefaultsSection />);
    await screen.findByRole("heading", { name: "Inventory" });
    expect(screen.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(["Inventory", "Connected devices", "Shop"]);
    expect(screen.getByLabelText("Platform default for Products")).toHaveValue("200");
    expect(screen.getByLabelText("Platform default for Storage for adapter media")).toHaveAttribute("placeholder", "Unlimited");
  });

  it("sends only the changed keys, converting MB to bytes, and null for a cleared default", async () => {
    mount(<LimitDefaultsSection />);
    const save = await screen.findByRole("button", { name: "Save defaults" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Platform default for Storage for adapter media"), { target: { value: "512" } });
    fireEvent.change(screen.getByLabelText("Platform default for Products"), { target: { value: "" } });
    fireEvent.click(save);
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0]).toEqual(["/admin/platform/limit-defaults", { defaults: { adapter_media_bytes: 512 * 1048576, products: null } }]);
  });

  it("refuses a non-number and filters by the search box", async () => {
    mount(<LimitDefaultsSection />);
    const save = await screen.findByRole("button", { name: "Save defaults" });
    fireEvent.change(screen.getByLabelText("Platform default for Products"), { target: { value: "lots" } });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search limits" }), { target: { value: "shop" } });
    expect(screen.queryByLabelText("Platform default for Products")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Platform default for Shop products")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search limits" }), { target: { value: "zzz" } });
    expect(screen.getByText("No limits match this search.")).toBeInTheDocument();
  });
});

describe("per-space limits grouped by module (decision 328a)", () => {
  beforeEach(() => { staffRequest.mockResolvedValue(SPACE); });

  it("groups under module headings, shows where the value comes from and the platform default beside an empty override", async () => {
    mount(<SpaceLimitsSection makerspaceId={7} headingLevel={2} />);
    await screen.findByRole("heading", { name: "Inventory" });
    expect(screen.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(["Inventory", "Connected devices"]);
    const inventory = screen.getByRole("heading", { name: "Inventory" }).closest("section")!;
    expect(within(inventory).getByText("Near limit")).toBeInTheDocument();
    expect(within(inventory).getByText(/platform default/)).toBeInTheDocument();
    const devices = screen.getByRole("heading", { name: "Connected devices" }).closest("section")!;
    expect(within(devices).getByText(/Platform default: 5 GB/)).toBeInTheDocument();
  });
});

describe("Space Manager limits and usage (read-only)", () => {
  it("groups by module with the 80% and 100% states and no inputs", async () => {
    staffRequest.mockResolvedValue({
      makerspace_id: 7, groups: GROUPS,
      rows: [
        { key: "shop_products", label: "shop products", used: 10, limit: 10, unit: "count", percent: 100, level: "limit", group: "shop", module: "shop", source: "default" },
        { key: "stock_transfers_monthly", label: "stock transfers", used: 9, limit: 10, unit: "count", percent: 90, level: "warning", group: "inventory", module: "stock_transfers", source: "override" },
      ],
    });
    mount(<SpaceLimitsUsage makerspaceId={7} />);
    await screen.findByRole("heading", { name: "Inventory" });
    expect(screen.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(["Inventory", "Shop"]);
    expect(within(screen.getByRole("heading", { name: "Inventory" }).closest("section")!).getByText("Near limit")).toBeInTheDocument();
    expect(within(screen.getByRole("heading", { name: "Shop" }).closest("section")!).getByText("At limit")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/limits");
    expect(screen.getByText("platform default")).toBeInTheDocument();
    expect(screen.getByText("Set for this space")).toBeInTheDocument();
  });
});
