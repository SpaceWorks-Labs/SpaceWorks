import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReportableConsumable } from "./types";

const api = vi.hoisted(() => ({ reportJobConsumables: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));

import { JobConsumablesReportCard } from "./JobConsumablesReportCard";

const row = (patch: Partial<ReportableConsumable>): ReportableConsumable => ({
  key: "vinyl", name: "Vinyl", kind: "material", unit: "m", required: false, attributes: {}, recorded_quantity: null, ...patch,
});

function show(rows: ReportableConsumable[], onUpdated = vi.fn()) {
  render(<QueryClientProvider client={new QueryClient()}>
    <JobConsumablesReportCard job={{ id: 7, report_consumables: rows }} onUpdated={onUpdated} /></QueryClientProvider>);
  return onUpdated;
}

describe("member reports what their job used (decision 341)", () => {
  beforeEach(() => api.reportJobConsumables.mockReset());

  it("renders nothing when the type lets members report nothing", () => {
    show([]);
    expect(screen.queryByText("What your job used")).toBeNull();
  });

  it("refuses fractions for whole units and sends only filled rows", async () => {
    api.reportJobConsumables.mockResolvedValue([]);
    const onUpdated = show([row({ key: "sheet", name: "Sheet", unit: "sheet" }), row({})]);
    const [sheet] = screen.getAllByRole("spinbutton");
    fireEvent.change(sheet, { target: { value: "1.5" } });
    expect(screen.getAllByRole("alert")[0].textContent).toMatch(/whole numbers/);
    expect((screen.getByRole("button", { name: "Report use" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(sheet, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Report use" }));
    await waitFor(() => expect(api.reportJobConsumables).toHaveBeenCalledWith(7, [{ key: "sheet", quantity: "2", attributes: {} }]));
    await waitFor(() => expect(onUpdated).toHaveBeenCalled());
  });

  it("shows recorded amounts instead of a field", () => {
    show([row({ recorded_quantity: "1.250" })]);
    expect(screen.getByText(/1.250/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Report use" })).toBeNull();
  });
});
