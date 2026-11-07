import { t } from "@lingui/core/macro";
import { ChartFrame, ChartLegend, valueText, type ChartProps } from "./ChartFrame";
import { ink, seriesColor } from "./chartStyle";

export function FunnelChart({ title, data }: ChartProps) {
  const rows = data.series.flatMap((series) => series.points.map((point) => ({ series, point })));
  const max = Math.max(1, ...rows.map(({ point }) => Math.abs(point.value)));
  return <ChartFrame title={title} data={data}>
    <svg viewBox={`0 0 720 ${Math.max(80, rows.length * 64 + 24)}`} className="w-full min-w-[45rem]" role="img" aria-label={t`${title}: funnel stages with signed values. Width shows magnitude.`}>
      {rows.map(({ series, point }, index) => {
        const width = Math.abs(point.value) / max * 300;
        const next = rows[index + 1];
        const bottom = next?.series.id === series.id ? Math.abs(next.point.value) / max * 300 : width;
        const y = index * 64 + 8;
        return <g key={`${series.id}-${index}`}>
          <text x="8" y={y + 18} fill={ink} fontSize="12">{point.label.slice(0, 22)}</text>
          {data.series.length > 1 && <text x="8" y={y + 36} fill={ink} fontSize="12">{series.label.slice(0, 22)}</text>}
          <polygon points={`${350 - width / 2},${y} ${350 + width / 2},${y} ${350 + bottom / 2},${y + 44} ${350 - bottom / 2},${y + 44}`} fill={seriesColor(series.id)} stroke={ink} />
          <text x="516" y={y + 24} fill={ink} fontSize="12">{valueText(point.value, series)}</text>
        </g>;
      })}
    </svg>
    <ChartLegend series={data.series} />
  </ChartFrame>;
}
