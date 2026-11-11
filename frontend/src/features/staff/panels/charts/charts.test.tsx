import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../../test/axe";
import { BarChart, LineChart, PieChart, StackedBarChart } from "../OperationsReportCharts";
import { CatalogChartPanel } from "./CatalogChartPanel";
import { toChartData, type ChartSpec } from "./chartSpec";
import { seriesColor } from "./chartStyle";
import { FunnelChart } from "./FunnelChart";
import { Heatmap } from "./Heatmap";
import { Histogram } from "./Histogram";
import { MultiLineChart } from "./MultiLineChart";

const spec: ChartSpec = { kind: "multi_line", series_fields: ["team"], x: { field: "date", kind: "time" },
  value_fields: [{ field: "value", unit: "loans" }], negative_values: "preserve", alt_text_template: "{points} values in {units}." };
const rows = [
  { team: "A", date: "2026-10-01", value: 2 }, { team: "A", date: "2026-10-02", value: 5 },
  { team: "A", date: "2026-10-10", value: 7 }, { team: "B", date: "2026-10-01", value: 3 },
];
const data = toChartData(spec, rows);
const legacyRows = [{ label: "One", value: 2 }, { label: "Two", value: 5 }];
const components = [
  ["MultiLineChart", <MultiLineChart title="Loans" data={data} />],
  ["Heatmap", <Heatmap title="Loans" data={data} />],
  ["FunnelChart", <FunnelChart title="Loans" data={data} />],
  ["Histogram", <Histogram title="Loans" data={data} />],
  ["BarChart", <BarChart rows={legacyRows} />], ["LineChart", <LineChart rows={legacyRows} />],
  ["StackedBarChart", <StackedBarChart rows={[{ label: "First", segments: legacyRows }]} />],
  ["PieChart", <PieChart rows={legacyRows} />],
] as const;

describe.each(components)("%s", (_, component) => {
  it("has a named figure, a keyboard-operable table alternative and clean semantics", async () => {
    const { container } = render(component);
    expect(screen.getByRole("figure")).toHaveAccessibleName();
    const scrollRegion = screen.getByRole("region");
    expect(scrollRegion).toHaveAccessibleName();
    expect(scrollRegion).toHaveAttribute("aria-labelledby", screen.getByRole("figure").getAttribute("aria-labelledby"));
    expect(scrollRegion).toHaveAttribute("tabindex", "0");
    scrollRegion.focus();
    expect(scrollRegion).toHaveFocus();
    const toggle = screen.getByRole("button", { name: "Show as table" });
    toggle.focus();
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await expectNoA11yViolations(container);
    fireEvent.click(toggle);
    const table = screen.getByRole("table");
    expect(table).toHaveAccessibleName();
    expect(table).toHaveAttribute("tabindex", "0");
    table.focus();
    expect(table).toHaveFocus();
    expect(screen.getAllByRole("columnheader").length).toBeGreaterThan(2);
    await expectNoA11yViolations(container);
    fireEvent.click(toggle);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

it("uses elapsed time, not row index, for multiline positions and preserves multiple series", () => {
  const { container } = render(<MultiLineChart title="Loans" data={data} />);
  const lines = container.querySelectorAll("polyline");
  expect(lines).toHaveLength(2);
  const xs = lines[0].getAttribute("points")!.split(" ").map((point) => Number(point.split(",")[0]));
  expect((xs[1] - xs[0]) / (xs[2] - xs[0])).toBeCloseTo(1 / 9);
  expect(container.querySelectorAll("circle, rect").length).toBe(4);
  expect(screen.getByRole("list", { name: "Series legend" })).toBeInTheDocument();
});

it("keeps bar, pie and segment colours stable after reordering", () => {
  const { container, rerender } = render(<PieChart rows={legacyRows} />);
  const initial = container.querySelector("circle")!.getAttribute("stroke");
  rerender(<PieChart rows={[...legacyRows].reverse()} />);
  expect(container.querySelectorAll("circle")[1].getAttribute("stroke")).toBe(initial);
  expect(initial).toBe(seriesColor("One"));
  rerender(<BarChart rows={legacyRows} />);
  const bar = container.querySelector('[style*="background-color"]')!.getAttribute("style");
  rerender(<BarChart rows={[...legacyRows].reverse()} />);
  expect(container.querySelectorAll('[style*="background-color"]')[1].getAttribute("style")).toBe(bar);
  rerender(<StackedBarChart rows={[{ label: "A", segments: legacyRows }]} />);
  const segment = container.querySelector('[style*="background-color"]')!.getAttribute("style");
  rerender(<StackedBarChart rows={[{ label: "A", segments: [...legacyRows].reverse() }]} />);
  expect(container.querySelectorAll('[style*="background-color"]')[1].getAttribute("style")).toBe(segment);
  expect(screen.getByText("One: 2")).toBeInTheDocument();
});

it.each([MultiLineChart, Heatmap, FunnelChart, Histogram])("handles empty chart data", (Component) => {
  render(<Component title="Empty" data={toChartData(spec, [])} />);
  expect(screen.getByText("No chart data.")).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it.each([MultiLineChart, Heatmap, FunnelChart, Histogram])("retains signed and zero measurements without invalid SVG geometry", (Component) => {
  const signed = toChartData(spec, [{ team: "A", date: "2026-10-01", value: -7 }, { team: "A", date: "2026-10-02", value: 0 }]);
  const { container } = render(<Component title="Signed values" data={signed} />);
  fireEvent.click(screen.getByRole("button", { name: "Show as table" }));
  expect(screen.getByRole("table")).toHaveTextContent("-7");
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  for (const rect of container.querySelectorAll("rect")) expect(Number(rect.getAttribute("height"))).toBeGreaterThanOrEqual(0);
});

describe("CatalogChartPanel", () => {
  it.each(["bar", "line", "stacked_bar", "pie", "multi_line", "heatmap", "funnel", "histogram"] as const)("renders %s using only its specification", (kind) => {
    render(<CatalogChartPanel title="Report" spec={{ ...spec, kind }} rows={rows} />);
    expect(screen.getAllByRole("figure").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Show as table" }).length).toBeGreaterThan(0);
  });

  it("renders currencies and units in separate figures", () => {
    render(<CatalogChartPanel title="Revenue" spec={{ ...spec, currency_field: "currency" }} rows={[
      { date: "2026-10-01", value: 1, currency: "USD" }, { date: "2026-10-01", value: 2, currency: "INR" },
    ]} />);
    expect(screen.getAllByRole("figure")).toHaveLength(2);
    expect(screen.getByRole("figure", { name: "Revenue — USD · loans" })).toBeInTheDocument();
  });

  it("renders loading, empty, errors with retry, and invalid specifications", () => {
    const retry = vi.fn();
    const { rerender } = render(<CatalogChartPanel title="Test" spec={spec} rows={[]} loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading chart");
    rerender(<CatalogChartPanel title="Test" spec={spec} rows={[]} />);
    expect(screen.getByText(/No activity/)).toBeInTheDocument();
    rerender(<CatalogChartPanel title="Test" spec={spec} rows={[]} error={new Error()} onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    rerender(<CatalogChartPanel title="Test" spec={{ ...spec, truncation: { topN: -1 } }} rows={[]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("invalid chart specification");
  });
});
