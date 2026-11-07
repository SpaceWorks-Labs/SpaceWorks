import { t } from "@lingui/core/macro";
import { ChartFrame, ChartLegend, type ChartProps } from "./ChartFrame";
import { ink, panel, seriesColor, seriesDash, seriesIndex } from "./chartStyle";

export function MultiLineChart({ title, data }: ChartProps) {
  const points = data.series.flatMap((series) => series.points);
  const times = points.map((point) => Number(point.x));
  const minTime = times.length ? Math.min(...times) : 0;
  const maxTime = Math.max(...times, minTime);
  const low = Math.min(0, ...points.map((point) => point.value));
  const high = Math.max(0, ...points.map((point) => point.value));
  const x = (time: string | number) => maxTime === minTime ? 360 : 72 + (Number(time) - minTime) / (maxTime - minTime) * 560;
  const y = (value: number) => 220 - (value - low) / (high - low || 1) * 180;
  const ticks = [...new Set(times)].sort((a, b) => a - b);
  const labelledTicks = ticks.filter((_, index) => index === 0 || index === ticks.length - 1 || ticks.length <= 4);
  return <ChartFrame title={title} data={data}>
    <svg viewBox="0 0 720 280" className="w-full min-w-[45rem]" role="img" aria-label={t`${title}: time on horizontal axis; values on vertical axis. ${data.summary}`}>
      <path d={`M72 30 V220 M72 ${y(0)} H632`} stroke={ink} fill="none" />
      {[low, high].map((value, index) => <text key={index} x="64" y={y(value)} textAnchor="end" fill={ink} fontSize="12">{value}</text>)}
      {labelledTicks.map((time) => <text key={time} x={x(time)} y="244" textAnchor="middle" fill={ink} fontSize="12">{new Date(time).toISOString().slice(0, maxTime - minTime < 172800000 ? 16 : 10).replace("T", " ")}</text>)}
      <text x="360" y="272" textAnchor="middle" fill={ink} fontSize="12">{data.xLabel}</text>
      {data.series.map((series, seriesNumber) => <g key={series.id}>
        <polyline points={series.points.map((point) => `${x(point.x)},${y(point.value)}`).join(" ")} fill="none" stroke={seriesColor(series.id)} strokeWidth="3" strokeDasharray={seriesDash(series.id)} />
        {series.points.map((point, index) => seriesIndex(series.id) % 2
          ? <rect key={index} x={x(point.x) - 4} y={y(point.value) - 4} width="8" height="8" fill={panel} stroke={seriesColor(series.id)} strokeWidth="2" />
          : <circle key={index} cx={x(point.x)} cy={y(point.value)} r="4" fill={panel} stroke={seriesColor(series.id)} strokeWidth="2" />)}
        {series.points.length > 0 && <text x={x(series.points[series.points.length - 1].x) + 10} y={y(series.points[series.points.length - 1].value) - 8} fill={ink} fontSize="12">#{seriesNumber + 1}</text>}
      </g>)}
    </svg>
    <ChartLegend series={data.series} />
  </ChartFrame>;
}
