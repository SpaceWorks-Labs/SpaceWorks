import { describe, expect, it } from "vitest";
import { toChartData, type ChartSpec } from "./chartSpec";

const spec: ChartSpec = {
  kind: "bar", series_fields: ["team"], x: { field: "bucket", kind: "category" },
  value_fields: [{ field: "amount", unit: "money" }], negative_values: "preserve",
  alt_text_template: "{series} series, {points} points by {x} in {units}.",
};

describe("toChartData", () => {
  it("partitions currencies even without an explicit partition", () => {
    const data = toChartData({ ...spec, currency_field: "currency" }, [
      { bucket: "A", team: "T", amount: "10.5", currency: "USD" },
      { bucket: "A", team: "T", amount: 20, currency: "INR" },
      { bucket: "A", team: "T", amount: 3, currency: "USD" },
      { bucket: "A", team: "T", amount: 1 },
    ]);
    expect(data.series).toHaveLength(3);
    expect(data.series.find((item) => item.currency === "USD")?.points[0].value).toBe(13.5);
    expect(new Set(data.series.map((item) => item.panelKey)).size).toBe(3);
  });

  it("partitions dynamic units and separate value fields", () => {
    const data = toChartData({ ...spec, value_fields: [{ field: "amount", unit: "mass", unit_field: "unit" }] }, [
      { bucket: "A", amount: 10, unit: "kg" }, { bucket: "A", amount: 100, unit: "g" },
    ]);
    expect(data.series.map((item) => item.unit).sort()).toEqual(["g", "kg"]);
    expect(new Set(data.series.map((item) => item.panelKey)).size).toBe(2);
    const multiple = toChartData({ ...spec, value_fields: [{ field: "amount", unit: "count" }, { field: "duration", unit: "hours" }] }, [{ bucket: "A", amount: 10, duration: 2 }]);
    expect(new Set(multiple.series.map((item) => item.panelKey)).size).toBe(2);
  });

  it("honours tenant, currency and unit partition fields", () => {
    for (const kind of ["tenant", "currency", "unit"] as const) {
      const data = toChartData({ ...spec, partition: { field: "partition", kind } }, [
        { bucket: "A", amount: 1, partition: "One" }, { bucket: "A", amount: 2, partition: "Two" },
      ]);
      expect(data.series).toHaveLength(2);
      expect(new Set(data.series.map((item) => item.panelKey)).size).toBe(2);
    }
  });

  it("keeps the shared top N and sums Other within each series, without mutating rows", () => {
    const rows = Object.freeze([
      Object.freeze({ team: "One", bucket: "A", amount: 10 }), { team: "One", bucket: "B", amount: 3 },
      { team: "One", bucket: "C", amount: -2 }, { team: "Two", bucket: "B", amount: 20 },
      { team: "Two", bucket: "A", amount: 1 },
    ]);
    const data = toChartData({ ...spec, truncation: { topN: 1, otherLabel: "Remaining" } }, rows);
    expect(data.series[0].points).toEqual([
      { x: "B", label: "B", value: 3 }, { x: "__chart_other__", label: "Remaining", value: 8, other: true },
    ]);
    expect(data.series[1].points.map((point) => point.value)).toEqual([20, 1]);
    expect(rows[0].amount).toBe(10);
  });

  it.each(["preserve", "clamp", "exclude"] as const)("handles negative values: %s", (negative_values) => {
    const data = toChartData({ ...spec, negative_values }, [{ bucket: "A", amount: -8 }, { bucket: "B", amount: 0 }]);
    expect(data.series[0].points.map((point) => point.value)).toEqual(negative_values === "preserve" ? [-8, 0] : negative_values === "clamp" ? [0, 0] : [0]);
  });

  it("handles empty rows and rejects missing, blank, boolean and nonfinite values", () => {
    expect(toChartData(spec, []).series).toEqual([]);
    const data = toChartData(spec, [null, "", " ", false, "NaN", Infinity, undefined].map((amount) => ({ bucket: "A", amount })));
    expect(data.series).toEqual([]);
    expect(data.summary).toBe("0 series, 0 points by Bucket in .");
  });

  it("sorts real timestamps chronologically and retains server stage order by default", () => {
    const rows = [{ bucket: "2026-10-10", amount: 1 }, { bucket: "2026-10-01", amount: 2 }, { bucket: "invalid", amount: 3 }];
    const data = toChartData({ ...spec, x: { field: "bucket", kind: "time" }, sort: { by: "value", direction: "desc" } }, rows);
    expect(data.series[0].points.map((point) => point.x)).toEqual([Date.parse("2026-10-01"), Date.parse("2026-10-10")]);
    expect(toChartData(spec, rows).series[0].points[0].label).toBe("2026-10-10");
    expect(toChartData({ ...spec, sort: { by: "value", direction: "asc" } }, rows).series[0].points.map((point) => point.value)).toEqual([1, 2, 3]);
  });

  it("rejects invalid truncation and never fabricates an Other timestamp", () => {
    expect(() => toChartData({ ...spec, truncation: { topN: 0 } }, [])).toThrow("positive integer");
    expect(() => toChartData({ ...spec, x: { field: "bucket", kind: "time" }, truncation: { topN: 2 } }, [])).toThrow("Time axes");
    expect(() => toChartData({ ...spec, kind: "multi_line" }, [])).toThrow("time axis");
  });

  it("uses stable identities when the incoming row order changes", () => {
    const rows = [{ bucket: "A", team: "One", amount: 2 }, { bucket: "A", team: "Two", amount: 3 }];
    expect(toChartData(spec, rows)).toEqual(toChartData(spec, [...rows].reverse()));
  });
});
