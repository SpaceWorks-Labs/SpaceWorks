import { t } from "@lingui/core/macro";
import type { ReportChartSpec } from "../analyticsApi";
import type { ChartRecord, ChartSpec } from "./chartSpec";

const kinds = new Set(["bar", "line", "stacked_bar", "pie", "multi_line", "heatmap", "funnel", "histogram"]);

/** Translate F1's serializer shape once, keeping currency, tenant and unit partitions intact. */
export function wireChartSpec(spec: ChartSpec | ReportChartSpec, hint?: string, rows: readonly ChartRecord[] = []): ChartSpec {
  if ("value_fields" in spec) return spec;
  const unitField = rows.some(row => row.measurement_unit != null) ? "measurement_unit" : "unit";
  const partitionField = spec.partition === "tenant" ? "makerspace_id"
    : spec.partition === "currency" ? spec.currency_field ?? "currency" : unitField;
  const fields = spec.values.map(value => ({ ...value,
    label: value.field.replace(/_/g, " "),
    ...(value.unit === "measurement_unit" ? { unit_field: "measurement_unit" }
      : value.unit === "unit" && rows.some(row => row.unit != null) ? { unit_field: "unit" } : {}),
  }));
  return {
    kind: hint === "donut" ? "pie" : kinds.has(hint ?? "") ? hint as ChartSpec["kind"] : spec.x.kind === "time" ? "multi_line" : "bar",
    x: spec.x, series_fields: spec.series, value_fields: fields,
    currency_field: spec.currency_field ?? undefined,
    partition: spec.partition ? { field: partitionField, kind: spec.partition } : undefined,
    negative_values: spec.negatives === "allow" ? "preserve" : "clamp",
    // Backend top_n applies to ranked series on time charts; dates must never become Other.
    truncation: spec.truncation && spec.x.kind !== "time"
      ? { topN: spec.truncation.top_n, otherLabel: spec.truncation.other_label } : undefined,
    alt_text_template: "{series} series, {points} observations by {x}, measured in {units}. Exact values are available in the table.",
  };
}

/** Some funnels declare stages as value columns rather than rows (confirmed, attended).
 * Pivot only the spec's declared fields; preserve the original row as a separate series.
 */
export function funnelInput(spec: ChartSpec, rows: readonly ChartRecord[]) {
  if (spec.kind !== "funnel" || spec.value_fields.length < 2) return { spec, rows };
  return {
    spec: { ...spec, x: { field: "__chart_stage", kind: "category" as const, label: t`Stage` },
      series_fields: [...spec.series_fields, spec.x.field], truncation: undefined,
      value_fields: [{ field: "__chart_value", unit: "values", label: t`Stages`, unit_field: "__chart_unit" }] },
    rows: rows.flatMap(row => spec.value_fields.map(field => ({ ...row, __chart_stage: field.label ?? field.field,
      __chart_value: row[field.field], __chart_unit: field.unit_field ? row[field.unit_field] : field.unit }))),
  };
}

export function reportAlternative(spec: ChartSpec | ReportChartSpec, rows: readonly ChartRecord[]) {
  if (!("alt_template" in spec)) return undefined;
  return rows.slice(0, 3).map(row => spec.alt_template.replace(/\{([^}]+)\}/g, (_, field: string) => {
    const value = row[field] ?? (field === "count" ? rows.length : "Unknown");
    return typeof value === "object" ? "Unknown" : String(value);
  })).join(" ");
}
