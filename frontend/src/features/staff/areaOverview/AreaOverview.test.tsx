import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { AllowedTabsContext } from "./allowedTabsContext";
import { AreaOverview } from "./AreaOverview";
import type { AreaGroup, AreaOverview as Overview } from "./areaOverviewApi";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const node = (overrides: Partial<AreaGroup>): AreaGroup => ({
  kind: "area", key: "area:machines", label: "machines", count: 1, attention: 0, money: [], finance: [], children: [], items: [],
  ...overrides,
});
const machine = node({ kind: "machine", key: "machine:7", label: "Laser A", count: 1,
  items: [{ id: 1, label: "Laser lens", status: "requested", quantity: 1, amount: "20.00", currency: "" }] });
const machines = node({ count: 1, attention: 1, money: [{ currency: "", amount: "20.00" }],
  children: [node({ kind: "machine_type", key: "machine_type:3", label: "Laser", count: 1, money: [{ currency: "", amount: "20.00" }],
    children: [machine] })] });
const inventory = node({ key: "area:inventory", label: "inventory", count: 2, money: [{ currency: "", amount: "6.00" }],
  children: [node({ kind: "category", key: "category:4", label: "Hand tools", count: 2 })] });
const overview = (groups: AreaGroup[], view: Overview["view"] = "tobuy"): Overview => ({
  view, areas: groups.map(group => group.key.slice(5)), totals: node({ kind: "root", key: "" }), groups, truncated: false,
});

function show(section: Overview["view"] = "tobuy", tabs: string[] = []) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/admin/to-buy?view=groups"]}><AllowedTabsContext.Provider value={tabs}>
      <AreaOverview makerspaceId={4} section={section} /></AllowedTabsContext.Provider></MemoryRouter></QueryClientProvider>);
}

describe("AreaOverview (decision 241)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); });

  it("gives the Space Manager every area, an area filter and per-group totals", async () => {
    api.staffRequest.mockResolvedValue(overview([machines, inventory]));
    show("tobuy", ["reports", "audit", "notifications"]);
    expect(await screen.findByRole("button", { name: /Machines/ })).toHaveAttribute("aria-expanded", "true");
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/area-overview/tobuy");
    expect(screen.getByText(/All your areas/).parentElement).toHaveTextContent("26.00");
    fireEvent.click(screen.getByRole("radio", { name: "Inventory" }));
    expect(screen.queryByRole("button", { name: /^Machines/ })).toBeNull();
    expect(screen.getByText(/This area/).parentElement).toHaveTextContent("6.00");
    const links = within(screen.getByRole("navigation", { name: "More for your area" })).getAllByRole("link");
    expect(links.map(link => link.getAttribute("href"))).toEqual(["/m/lab/admin/reports", "/m/lab/admin/audit",
      "/m/lab/admin/notifications"]);
  });

  it("folds groups open to the machine type, then the machine and its rows", async () => {
    api.staffRequest.mockResolvedValue(overview([machines]));
    show();
    const type = await screen.findByRole("button", { name: /^Laser\s*1 row/ });
    expect(type).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("radio")).toBeNull(); // one area: nothing to filter
    fireEvent.click(type);
    fireEvent.click(screen.getByRole("button", { name: /^Laser A/ }));
    expect(screen.getByRole("list", { name: "Rows in Laser A" })).toHaveTextContent("Laser lens");
    fireEvent.click(screen.getByRole("button", { name: "Close all" }));
    expect(screen.queryByText("Laser lens")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "More for your area" })).toBeNull();
  });

  it("shows owed money, and no net figure when the server withholds payouts", async () => {
    api.staffRequest.mockResolvedValue(overview([node({ key: "area:inventory", label: "inventory", count: 1, attention: 1,
      finance: [{ currency: "inr", income: "100.00", other_income: "0.00", refunds: "0.00", expenses: "40.00", owed: "75.00",
        money_in: "100.00" }] })], "finance"));
    show("finance");
    const heading = await screen.findByRole("button", { name: /^Inventory/ });
    expect(heading).toHaveTextContent("1 unpaid");
    expect(heading).toHaveTextContent(/Owed/);
    expect(heading).not.toHaveTextContent(/Net/);
    expect(String(api.staffRequest.mock.calls[0][0])).toMatch(/area-overview\/finance\?from=\d{4}-\d{2}-\d{2}&to=/);
  });

  it("explains an empty list and a refusal in plain words", async () => {
    api.staffRequest.mockResolvedValueOnce(overview([]));
    show("repairs");
    expect(await screen.findByText("No open repairs in the areas you manage.")).toBeInTheDocument();
    api.staffRequest.mockRejectedValueOnce(new StructuredApiError(404, { detail: "Not found." }));
    show("consumables");
    expect(await screen.findByRole("alert")).toHaveTextContent("This list is not switched on for the areas you manage.");
  });

  it("asks for done rows only when the person ticks the box", async () => {
    api.staffRequest.mockResolvedValue(overview([machines]));
    show("repairs");
    fireEvent.click(await screen.findByRole("checkbox", { name: "Include fixed and closed" }));
    expect(api.staffRequest).toHaveBeenLastCalledWith("/admin/makerspace/4/area-overview/repairs?status=all");
  });
});
