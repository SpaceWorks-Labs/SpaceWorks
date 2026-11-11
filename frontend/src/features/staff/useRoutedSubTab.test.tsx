import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinancePanel } from "../finance/FinancePanel";
import { keptStaffSubPath, staffSubPathFromPath, staffTabPath } from "./staffTabs";
import { useRoutedSubTab } from "./useRoutedSubTab";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest }));

function Probe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }
function mount(node: ReactNode, url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={[url]}><QueryClientProvider client={client}>{node}<Probe /></QueryClientProvider></MemoryRouter>);
}
function HookProbe() {
  const route = useRoutedSubTab();
  return <><span data-testid="segment">{route.segment}</span><a href={route.href("pos")}>pos</a>
    <button type="button" onClick={() => route.select("stock")}>stock</button></>;
}

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue([]); });

describe("routed Shop and Finance views (0.12.0 row 15)", () => {
  it("keeps the view segment through console canonicalisation", () => {
    expect(staffTabPath("shop", false, "lab", false, "pos")).toBe("/m/lab/admin/shop/pos");
    expect(staffTabPath("finance", false, undefined, true, "disputes")).toBe("/admin/finance/disputes");
    expect(keptStaffSubPath("shop", "shop", staffSubPathFromPath("/m/lab/admin/shop/pos", false))).toBe("pos");
  });

  it("reads the segment and builds sibling paths, keeping only the session context", async () => {
    mount(<HookProbe />, "/m/lab/admin/shop/orders?context=platform&order=4");
    expect(screen.getByTestId("segment")).toHaveTextContent("orders");
    expect(screen.getByRole("link", { name: "pos" })).toHaveAttribute("href", "/m/lab/admin/shop/pos?context=platform");
    fireEvent.click(screen.getByRole("button", { name: "stock" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/m/lab/admin/shop/stock?context=platform"));
  });

  it("adds the segment when the tab is opened bare", () => {
    mount(<HookProbe />, "/admin/shop");
    expect(screen.getByTestId("segment")).toBeEmptyDOMElement();
    expect(screen.getByRole("link", { name: "pos" })).toHaveAttribute("href", "/admin/shop/pos");
  });

  it("opens a Finance section from its URL and writes the chosen one back", async () => {
    const space = { id: 2, name: "Lab", enabled_modules: [], enabled_features: ["billing.capture_flags", "billing.disputes"] };
    mount(<FinancePanel makerspace={space} canViewFinance canRecordPayment={false} />, "/m/lab/admin/finance/disputes");
    expect(screen.getByRole("tab", { name: "Disputes" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Unexpected payments" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/m/lab/admin/finance/flags"));
    expect(screen.getByRole("tab", { name: "Unexpected payments" })).toHaveAttribute("aria-selected", "true");
  });

  it("falls back to the first section for an unknown segment", () => {
    const space = { id: 2, name: "Lab", enabled_modules: [], enabled_features: ["billing.capture_flags", "billing.disputes"] };
    mount(<FinancePanel makerspace={space} canViewFinance canRecordPayment={false} />, "/m/lab/admin/finance/nope");
    expect(screen.getByRole("tab", { name: "Unexpected payments" })).toHaveAttribute("aria-selected", "true");
  });
});
