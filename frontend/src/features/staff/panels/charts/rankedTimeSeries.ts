import type { ReportChartSpec } from "../analyticsApi";
import type { ChartData, ChartPoint, ChartSeries, ChartSpec } from "./chartSpec";

/** Top N on a time axis ranks series, preserving dates. Measures are ranked separately:
 * service, manual and booked hours must never be summed into an invented hour measure.
 */
export function rankedTimeSeries(spec: ChartSpec | ReportChartSpec, data: ChartData): ChartData {
  if (!("values" in spec) || !spec.truncation || spec.x.kind !== "time") return data;
  const { top_n: count, other_label: otherLabel } = spec.truncation;
  if (!Number.isInteger(count) || count < 1) throw new Error("Invalid top N.");
  const groups = new Map<string, ChartSeries[]>();
  for (const series of data.series) {
    const key = JSON.stringify([series.panelKey, series.valueField]);
    groups.set(key, [...(groups.get(key) ?? []), series]);
  }
  const series = [...groups.values()].flatMap(members => {
    // Most-lent and machine usage already supply an explicit, scoped Other series.
    if (members.length <= count || members.some(member => member.dimensions?.includes(otherLabel))) return members;
    const magnitude = (member: ChartSeries) => member.points.reduce((total, point) => total + Math.abs(point.value), 0);
    const ranked = [...members].sort((a, b) => magnitude(b) - magnitude(a) || a.id.localeCompare(b.id));
    const points = new Map<string | number, ChartPoint>();
    for (const member of ranked.slice(count)) for (const point of member.points) {
      const found = points.get(point.x);
      points.set(point.x, { ...point, value: (found?.value ?? 0) + point.value });
    }
    const other = { ...members[0], id: JSON.stringify([otherLabel, members[0].panelKey, members[0].valueField]),
      label: `${otherLabel} · ${members[0].valueField?.replace(/_/g, " ") ?? members[0].unit}`,
      dimensions: [otherLabel], points: [...points.values()].sort((a, b) => Number(a.x) - Number(b.x)) };
    return [...ranked.slice(0, count), other];
  });
  return { ...data, series };
}
