import { t } from "@lingui/core/macro";
import { ChartFrame, ChartLegend, valueText, type ChartProps } from "./ChartFrame";
import { edge, ink, seriesColor } from "./chartStyle";

/** Reports supply labelled, pre-aggregated bins; no client-side rebucketing of counts. */
export function Histogram({ title, data }: ChartProps) {
  const rows = data.series.flatMap((series) => series.points.map((point) => ({ series, point })));
  const low = Math.min(0, ...rows.map(({ point }) => point.value));
  const high = Math.max(0, ...rows.map(({ point }) => point.value));
  const y = (value: number) => 220 - (value - low) / (high - low || 1) * 170;
  const width = Math.max(480, rows.length * 120 + 100);
  return <ChartFrame title={title} data={data}>
    <svg viewBox={`0 0 ${width} 290`} style={{ minWidth: width }} className="w-full" role="img" aria-label={t`${title}: ${data.xLabel} bins on horizontal axis, frequency on vertical axis.`}>
      <path d={`M64 30 V220 M64 ${y(0)} H${width - 12}`} stroke={ink} fill="none" />
      {[low, high].map((value, index) => <text key={index} x="56" y={y(value)} textAnchor="end" fill={ink} fontSize="12">{value}</text>)}
      {rows.map(({ series, point }, index) => {
        const x = 80 + index * 120;
        return <g key={`${series.id}-${index}`}>
          <rect x={x} y={Math.min(y(0), y(point.value))} width="108" height={Math.abs(y(point.value) - y(0))} fill={seriesColor(series.id)} stroke={edge} />
          <text x={x + 54} y={point.value < 0 ? y(point.value) + 16 : y(point.value) - 8} textAnchor="middle" fill={ink} fontSize="12">{valueText(point.value, series)}</text>
          <text x={x + 54} y="256" textAnchor="middle" fill={ink} fontSize="12">{point.label.slice(0, 16)}</text>
          {data.series.length > 1 && <text x={x + 54} y="272" textAnchor="middle" fill={ink} fontSize="12">{series.label.slice(0, 16)}</text>}
        </g>;
      })}
      <text x={width / 2} y="288" textAnchor="middle" fill={ink} fontSize="12">{data.xLabel}</text>
    </svg>
    <ChartLegend series={data.series} />
  </ChartFrame>;
}
