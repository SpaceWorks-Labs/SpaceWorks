import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SpaceLimitsUsage } from "../hostingPlan/SpaceLimitsUsage";
import { AreaAllowances } from "../allowances/AreaAllowances";
import { UsageTable } from "../TenantUsagePanel";
import { LimitUsage, currencyUsageAmount } from "./LimitRowView";
import { unifyLimits } from "./limitsModel";
import type { CurrencyUsage, SpaceLimits } from "./limitsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

// Same exact JSON contract as test_cross_audit_money_creators_cx9_wp5.py.
const amounts: CurrencyUsage[] = [
  { currency: "KWD", used: "1.234", remaining: "98.766", percent: 1.2 },
  { currency: "USD", used: "9.99", remaining: "90.01", percent: 10 },
];
const row = { key: "payments_monthly_amount", label: "money taken this month", unit: "amount" as const,
  group: "payments", module: "payments", source: "override" as const, used: null, limit: 100,
  percent: 10, level: "ok" as const, amounts };
const mount = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient({
  defaultOptions: { queries: { retry: false } },
})}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

afterEach(() => { vi.restoreAllMocks(); staffRequest.mockReset(); });

describe("area_payments_ledger: exact currency usage (547.3)", () => {
  it("preserves the API decimal strings through the editable limit model and display", () => {
    const payload: SpaceLimits = { custom_domain: false, rows: [], quota_rows: [row] };
    const [unified] = unifyLimits(payload);
    expect(unified.amounts).toEqual(amounts);
    render(<LimitUsage row={unified} />);
    expect(screen.getByText("KWD 1.234 / KWD 100")).toBeInTheDocument();
    expect(screen.getByText("USD 9.99 / USD 100")).toBeInTheDocument();
    expect(screen.queryByText(/11\.224|11\.2\b|USD 10\b|KWD 1\.2 /)).not.toBeInTheDocument();
  });

  it("renders the Space Manager usage JSON without truncation or currency mixing", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, groups: [{ key: "payments", label: "Payments" }], rows: [row] });
    mount(<SpaceLimitsUsage makerspaceId={7} />);
    expect(await screen.findByText("KWD 1.234 / KWD 100")).toBeInTheDocument();
    expect(screen.getByText("USD 9.99 / USD 100")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/limits");
  });

  it("retains labelled amounts in role allowances and the usage table", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, areas: [], rows: [{ ...row, remaining: null, areas: [] }] });
    mount(<AreaAllowances makerspaceId={7} tab="dashboard" />);
    expect(await screen.findByText("KWD 1.234 / KWD 100 · USD 9.99 / USD 100")).toBeInTheDocument();
    render(<UsageTable data={{ makerspace_id: 7, managed: false, resources: [row] }} />);
    expect(screen.getByText("KWD 1.234 · USD 9.99")).toBeInTheDocument();
  });

  it("formats decimal strings beyond Number precision without rounding their digits", () => {
    expect(currencyUsageAmount("KWD", "999999999999999.234")).toBe("KWD 999,999,999,999,999.234");
  });

  it("announces loading until currency usage arrives", () => {
    staffRequest.mockReturnValue(new Promise(() => {}));
    mount(<SpaceLimitsUsage makerspaceId={7} />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.queryByText("USD 9.99 / USD 100")).not.toBeInTheDocument();
  });

  it("renders the unlimited empty state without inventing a zero currency amount", async () => {
    staffRequest.mockResolvedValue({ makerspace_id: 7, groups: [], rows: [] });
    mount(<SpaceLimitsUsage makerspaceId={7} />);
    expect(await screen.findByText("No limits are set for this space: everything is unlimited.")).toBeInTheDocument();
    expect(screen.queryByText(/USD|KWD/)).not.toBeInTheDocument();
  });

  it("recovers a failed usage query through Retry and preserves exact amounts", async () => {
    staffRequest.mockRejectedValueOnce(new Error("Usage temporarily unavailable"));
    staffRequest.mockResolvedValueOnce({ makerspace_id: 7, groups: [{ key: "payments", label: "Payments" }], rows: [row] });
    mount(<SpaceLimitsUsage makerspaceId={7} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load this space's limits. Try again.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("USD 9.99 / USD 100")).toBeInTheDocument();
    expect(screen.getByText("KWD 1.234 / KWD 100")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
