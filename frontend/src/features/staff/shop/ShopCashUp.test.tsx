import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopCashUp } from "./ShopCashUp";

const mocks = vi.hoisted(() => ({ staff: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest: mocks.staff }));

const session = (extra: Record<string, unknown>) => ({ id: 5, status: "open", currency: "inr", opening_float: "500.00", opened_by: 1,
  opened_at: "2026-11-04T09:00:00Z", counted_cash: null, expected_cash: null, variance: null, note: "", closed_by: null, closing_at: null,
  confirmed_by: null, closed_at: null, expected_now: "740.00", ...extra });
const page = (rows: unknown[]) => ({ count: rows.length, next: null, previous: null, results: rows });
const posted = (suffix: string) => mocks.staff.mock.calls.filter(([path, init]) => String(path).endsWith(suffix) && init?.method === "POST");

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ShopCashUp makerspaceId={4} canManage onLeave={vi.fn()} /></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); });

describe("cash-up", () => {
  it("opens a drawer with a float", async () => {
    mocks.staff.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? session({}) : page([])));
    show();
    const field = await screen.findByLabelText("Opening float");
    const next = screen.getByRole("button", { name: "Open the drawer" });
    expect(next).toBeDisabled();
    fireEvent.change(field, { target: { value: "500" } });
    fireEvent.click(next);
    await waitFor(() => expect(posted("/cash-sessions/")).toHaveLength(1));
    expect(JSON.parse(posted("/cash-sessions/")[0][1].body)).toEqual({ opening_float: "500" });
  });

  it("shows the expected cash, records the count and shows the variance for a second person to confirm", async () => {
    let state = session({});
    mocks.staff.mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/close/")) state = session({ status: "closing", counted_cash: "735.00", expected_cash: "740.00", variance: "-5.00", note: "Short 5" });
      else if (path.endsWith("/confirm/")) state = session({ status: "closed", counted_cash: "735.00", expected_cash: "740.00", variance: "-5.00" });
      return Promise.resolve(init?.method === "POST" ? state : page([state]));
    });
    show();
    expect(await screen.findByText(/740\.00/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Counted cash"), { target: { value: "735" } });
    fireEvent.change(screen.getByLabelText("Note (optional)"), { target: { value: "Short 5" } });
    fireEvent.click(screen.getByRole("button", { name: "Close and record the count" }));
    expect(await screen.findByText(/5\.00 short/)).toBeVisible();
    expect(JSON.parse(posted("/close/")[0][1].body)).toEqual({ counted_cash: "735", note: "Short 5" });
    fireEvent.click(screen.getByRole("button", { name: "Confirm the count" }));
    expect(await screen.findByText("Drawer closed")).toBeVisible();
    expect(posted("/shop/cash-sessions/5/confirm/")).toHaveLength(1);
  });
});
