import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FyReceiptsSetting, fyReceiptPrefix, fyShort } from "./FyReceiptsSetting";
import { PlanSacField, planSacOn, validatePlanSac } from "./PlanSacField";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const year = { financial_year_start_month: 4, current_label: "2026-27", current_start: "2026-04-01", current_end: "2027-03-31", presets: [] };

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/financial-year") ? year
    : path.endsWith("/billing-settings") ? { number_prefix: "SW" } : {}));
});

describe("FyReceiptsSetting", () => {
  it("mirrors the server's prefix and year rules", () => {
    expect(fyReceiptPrefix("SW")).toBe("SW");
    expect(fyReceiptPrefix("receipts")).toBe("R");
    expect(fyReceiptPrefix("")).toBe("R");
    expect(fyShort("2026-27")).toBe("26-27");
    expect(fyShort("2026")).toBe("26");
  });

  it("shows the sample number and switches the capability on", async () => {
    wrap(<FyReceiptsSetting makerspace={{ id: 3, enabled_features: ["billing.documents"] }} />);
    expect(await screen.findByText("SW26-27/0001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3", expect.objectContaining({ method: "PATCH" })));
    const patch = staffRequest.mock.calls.find(([path]) => path === "/admin/makerspaces/3")!;
    expect(JSON.parse(patch[1].body as string)).toEqual({ enabled_features: ["billing.documents", "billing.fy_receipts"] });
  });

  it("cannot be switched on without receipt documents", async () => {
    wrap(<FyReceiptsSetting makerspace={{ id: 3, enabled_features: [] }} />);
    expect(screen.getByRole("switch")).toBeDisabled();
    expect(screen.getByText(/Turn on “Receipt documents” under Features first/)).toBeInTheDocument();
  });
});

describe("PlanSacField", () => {
  it("accepts blank or 4 to 8 digits only", () => {
    expect(validatePlanSac("")).toBeNull();
    expect(validatePlanSac("998311")).toBeNull();
    expect(validatePlanSac("123")).toMatch(/4 to 8 digits/);
    expect(validatePlanSac("12ab")).toMatch(/4 to 8 digits/);
  });

  it("is offered only while plan SAC and tax are both on", () => {
    expect(planSacOn(["billing.plan_sac", "billing.tax"])).toBe(true);
    expect(planSacOn(["billing.plan_sac"])).toBe(false);
  });

  it("shows the format error inline", () => {
    wrap(<PlanSacField value="99" onChange={() => undefined} />);
    expect(screen.getByText(/A SAC code is 4 to 8 digits/)).toBeInTheDocument();
  });
});
