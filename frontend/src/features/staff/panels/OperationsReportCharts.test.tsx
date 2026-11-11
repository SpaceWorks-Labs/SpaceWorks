import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BarChart, LineChart, StackedBarChart } from "./OperationsReportCharts";
import { PerMakerspaceTables } from "./OperationsReportTable";

describe("operations report charts", () => {
  it("gives line and stacked charts accessible descriptions", () => {
    render(<>
      <LineChart rows={[{ label: "2026-09-01", value: 3 }]} valueLabel="requests" />
      <StackedBarChart rows={[{ label: "2026-09-01", segments: [
        { label: "issued", value: 2 }, { label: "returned", value: 1 },
      ] }]} valueLabel="loans" />
    </>);

    expect(screen.getByRole("figure", { name: /Line chart of requests/ })).toBeTruthy();
    const stacked = within(screen.getByRole("figure", { name: "Stacked bar chart of loans" }));
    expect(stacked.getByText("issued: 2 loans")).toBeVisible();
    expect(stacked.getByText("returned: 1 loans")).toBeVisible();
    fireEvent.click(stacked.getByRole("button", { name: "Show as table" }));
    expect(stacked.getByRole("rowheader", { name: "issued" })).toBeVisible();
    expect(stacked.getByRole("rowheader", { name: "returned" })).toBeVisible();
  });

  it("keeps the table fallback when every chart value is zero", () => {
    render(<>
      <BarChart rows={[{ label: "No activity", value: 0 }]} valueLabel="events" />
      <PerMakerspaceTables
        data={{ rows: [["makerspace_id", "status", "count"], [1, "idle", 0], [2, "active", 4]] }}
        nameOf={(id) => `Space ${id}`}
      />
    </>);

    const chart = within(screen.getByRole("figure", { name: "Bar chart of events" }));
    fireEvent.click(chart.getByRole("button", { name: "Show as table" }));
    expect(chart.getByRole("cell", { name: "No activity" })).toBeVisible();
    expect(chart.getByRole("cell", { name: "0" })).toBeVisible();
    expect(screen.getByText("Space 1")).toBeTruthy();
    expect(screen.getByText("Space 2")).toBeTruthy();
    expect(screen.getByText("active")).toBeTruthy();
  });
});
