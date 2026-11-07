import { t } from "@lingui/core/macro";
import { ChartFrame, type ChartProps } from "./ChartFrame";
import { ink, panel } from "./chartStyle";

const scaleFill = (fraction: number) => `color-mix(in srgb, rgb(var(--chart-info)) ${fraction * 100}%, ${panel})`;

/** series_fields supply the vertical axis (weekday or cohort); x supplies hour or age. */
export function Heatmap({ title, data }: ChartProps) {
  const columns = [...new Map(data.series.flatMap((series) => series.points.map((point) => [point.x, point.label] as const))).entries()];
  if (data.xKind === "time") columns.sort((a, b) => Number(a[0]) - Number(b[0]));
  const values = data.series.flatMap((series) => series.points.map((point) => point.value));
  const max = Math.max(1, ...values.map(Math.abs));
  const width = Math.max(400, 160 + columns.length * 72);
  const height = 76 + data.series.length * 48;
  return <ChartFrame title={title} data={data}>
    <svg viewBox={`0 0 ${width} ${height}`} style={{ minWidth: width }} className="w-full" role="img" aria-label={t`${title}: rows are series, columns are ${data.xLabel}. Every cell displays its value.`}>
      <text x="8" y="18" fill={ink} fontSize="12">{t`Series / ${data.xLabel}`}</text>
      {columns.map(([key, label], index) => <text key={key} x={196 + index * 72} y="38" textAnchor="middle" fill={ink} fontSize="12">{label.length > 10 ? `${label.slice(0, 9)}…` : label}</text>)}
      {data.series.map((series, row) => <g key={series.id}>
        <text x="8" y={70 + row * 48} fill={ink} fontSize="12">{series.label.slice(0, 21)}</text>
        {columns.map(([key], column) => {
          const point = series.points.find((point) => point.x === key);
          const x = 162 + column * 72;
          const y = 48 + row * 48;
          return <g key={key}>
            <rect x={x} y={y} width="68" height="44" fill={point ? scaleFill(Math.abs(point.value) / max) : panel} stroke={ink} />
            <rect x={x + 4} y={y + 4} width="60" height="26" fill={panel} />
            {point && <rect x={x + 2} y={y + 36} width={Math.abs(point.value) / max * 64} height="6" fill="rgb(var(--chart-info))" />}
            <text x={x + 34} y={y + 24} textAnchor="middle" fill={ink} fontSize="12">{point ? point.value : "—"}</text>
          </g>;
        })}
      </g>)}
    </svg>
    <ul aria-label={t`Magnitude scale`} className="flex flex-wrap gap-3 text-sm">{[0, 0.25, 0.5, 0.75, 1].map((fraction) => <li key={fraction} className="flex items-center gap-1">
      <svg width="20" height="16" aria-hidden="true"><rect x="1" y="1" width="18" height="14" fill={scaleFill(fraction)} stroke={ink} /></svg>{Number((max * fraction).toFixed(2))}
    </li>)}</ul>
    <p className="text-sm text-muted">{t`Scale: strip length shows magnitude from 0 to ${max}. Signed cell values give the exact measurement; — means no observation.`}</p>
  </ChartFrame>;
}
