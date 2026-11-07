import { t } from "@lingui/core/macro";
/** Wire contract for catalog chart_spec. All field names refer to typed report rows. */
export type ChartSpec = {
  kind: "bar" | "line" | "stacked_bar" | "pie" | "multi_line" | "heatmap" | "funnel" | "histogram";
  series_fields: string[];
  x: { field: string; kind: "time" | "category"; label?: string };
  value_fields: { field: string; unit: string; label?: string; unit_field?: string }[];
  currency_field?: string;
  partition?: { field: string; kind: "tenant" | "currency" | "unit" };
  negative_values: "preserve" | "clamp" | "exclude";
  truncation?: { topN: number; otherLabel?: string };
  sort?: { by: "x" | "value"; direction: "asc" | "desc" };
  /** Supported placeholders: {series}, {points}, {x}, {units}. */
  alt_text_template: string;
};

export type ChartPoint = { x: string | number; label: string; value: number; other?: boolean };
export type ChartSeries = {
  id: string; label: string; unit: string; currency?: string; partition?: string;
  valueField?: string; dimensions?: string[];
  panelKey: string; points: ChartPoint[];
};
export type ChartData = { series: ChartSeries[]; summary: string; xKind: "time" | "category"; xLabel: string };
export type ChartRecord = Readonly<Record<string, unknown>>;

const text = (value: unknown) => value == null || value === "" ? "Unknown" : String(value);
const compare = (a: string | number, b: string | number) =>
  typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), "en", { numeric: true });

/** Pure projection. Never coerce null/blank/boolean to a measurement, or sum across units. */
export function toChartData(spec: ChartSpec, rows: readonly ChartRecord[]): ChartData {
  if (!spec.x.field || !spec.value_fields.length) throw new Error(t`Chart fields are required.`);
  if (spec.kind === "multi_line" && spec.x.kind !== "time") throw new Error(t`Multi-line charts require a time axis.`);
  if (spec.truncation && (!Number.isInteger(spec.truncation.topN) || spec.truncation.topN < 1)) {
    throw new Error(t`Chart topN must be a positive integer.`);
  }
  if (spec.truncation && spec.x.kind === "time") throw new Error(t`Time axes cannot contain an Other bucket.`);
  const groups = new Map<string, ChartSeries>();
  for (const row of rows) {
    const rawX = row[spec.x.field];
    if (rawX == null || rawX === "") continue;
    const x = spec.x.kind === "time" ? (typeof rawX === "number" ? rawX : Date.parse(String(rawX))) : String(rawX);
    if (typeof x === "number" && !Number.isFinite(x)) continue;
    for (const field of spec.value_fields) {
      const raw = row[field.field];
      if ((typeof raw !== "number" && typeof raw !== "string") || String(raw).trim() === "") continue;
      let value = Number(raw);
      if (!Number.isFinite(value) || (value < 0 && spec.negative_values === "exclude")) continue;
      if (spec.negative_values === "clamp") value = Math.max(0, value);
      const partition = spec.partition ? text(row[spec.partition.field]) : undefined;
      const unit = field.unit_field ? text(row[field.unit_field])
        : spec.partition?.kind === "unit" ? partition! : field.unit;
      const currency = spec.currency_field ? text(row[spec.currency_field])
        : spec.partition?.kind === "currency" ? partition : undefined;
      const identity = spec.series_fields.map((key) => text(row[key]));
      const panelKey = JSON.stringify([unit, currency, partition]);
      const id = JSON.stringify([identity, field.field, panelKey]);
      let series = groups.get(id);
      if (!series) {
        series = { id, label: [...identity, field.label ?? field.field].join(" · "), unit, currency, partition,
          valueField: field.field, dimensions: identity, panelKey, points: [] };
        groups.set(id, series);
      }
      const point = series.points.find((point) => point.x === x);
      if (point) point.value += value;
      else series.points.push({ x, label: spec.x.kind === "time" ? new Date(x).toISOString() : String(x), value });
    }
  }
  const series = [...groups.values()].sort((a, b) => compare(a.id, b.id));
  // Pick a shared top N per compatible panel, so a category means the same thing in every series.
  const panels = new Set(series.map((item) => item.panelKey));
  for (const panel of panels) {
    const members = series.filter((item) => item.panelKey === panel);
    if (spec.truncation) {
      const totals = new Map<string | number, number>();
      for (const item of members) for (const point of item.points) totals.set(point.x, (totals.get(point.x) ?? 0) + Math.abs(point.value));
      const keep = new Set([...totals].sort((a, b) => b[1] - a[1] || compare(a[0], b[0])).slice(0, spec.truncation.topN).map(([x]) => x));
      let otherX = "__chart_other__";
      while (totals.has(otherX)) otherX += "_";
      for (const item of members) {
        const omitted = item.points.filter((point) => !keep.has(point.x));
        item.points = item.points.filter((point) => keep.has(point.x));
        if (omitted.length) item.points.push({ x: otherX, label: spec.truncation.otherLabel ?? t`Other`, value: omitted.reduce((sum, point) => sum + point.value, 0), other: true });
      }
    }
    for (const item of members) item.points.sort((a, b) => {
      if (a.other || b.other) return Number(Boolean(a.other)) - Number(Boolean(b.other));
      if (spec.x.kind !== "time" && !spec.sort) return 0; // Funnel stages and server-defined buckets retain their order.
      const difference = spec.x.kind !== "time" && spec.sort?.by === "value" ? a.value - b.value : compare(a.x, b.x);
      return (spec.x.kind !== "time" && spec.sort?.direction === "desc" ? -1 : 1) * difference || compare(a.x, b.x);
    });
  }
  return { series, summary: chartSummary(spec, series), xKind: spec.x.kind, xLabel: spec.x.label ?? spec.x.field };
}

/** Recompute after panel partitioning so summaries describe only the displayed data. */
export function chartSummary(spec: ChartSpec, series: ChartSeries[]) {
  const replacements: Record<string, string> = {
    series: String(series.length), points: String(series.reduce((sum, item) => sum + item.points.length, 0)),
    x: spec.x.label ?? spec.x.field, units: [...new Set(series.map((item) => [item.unit, item.currency].filter(Boolean).join(" ")))].join(", "),
  };
  return spec.alt_text_template.replace(/\{(series|points|x|units)\}/g, (_, key: string) => replacements[key]);
}
