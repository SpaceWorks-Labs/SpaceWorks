import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reportItem } from "../../../test/analyticsFixtures";

import { OperationsReports } from "./OperationsReports";
import type { Makerspace } from "./shared";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), staffRequest }));

const space = { id: 7, name: "Lab", enabled_modules: ["reports"] } as Makerspace;
function panel(canViewFinance: boolean) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <OperationsReports makerspace={space} makerspaces={[space]} isSuperadmin={false}
      canViewAudit={false} canManageMachines={false} canViewFinance={canViewFinance} />
  </QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  window.localStorage.clear();
  staffRequest.mockImplementation((url: string) => Promise.resolve(url.endsWith("/catalog") ? {
    results: [reportItem("payment-reconciliation", { title: "Payment reconciliation",
      exportable: true, fields: [], grains: ["day"], chart_hint: "table", chart_spec: null })],
  } : { typed_rows: [], rows: [] }));
});

describe("finance report delegation", () => {
  it("loads the money report for a finance reader without requesting hardware metrics", async () => {
    panel(true);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/analytics/payment-reconciliation?grain=day"));
    expect(within(screen.getByRole("region", { name: "Payments" })).getByRole("button", { name: "Payment reconciliation" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByText("Products")).not.toBeInTheDocument();
    expect(staffRequest.mock.calls.some(([url]) => String(url).includes("/analytics/summary"))).toBe(false);
  });

  it("does not mount the money report without view_finance", async () => {
    staffRequest.mockResolvedValue({ results: [] });
    panel(false);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/reports/catalog"));
    expect(screen.queryByRole("heading", { name: "Payment reconciliation" })).not.toBeInTheDocument();
    expect(staffRequest.mock.calls.some(([url]) => String(url).includes("/analytics/payment-reconciliation"))).toBe(false);
  });
});
