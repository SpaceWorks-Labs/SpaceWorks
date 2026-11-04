import type { AnalyticsPeriod } from "./analyticsApi";

export function AnalyticsPeriodControls({ value, onChange, grains = ["day", "week", "month"] }: {
  value: AnalyticsPeriod; onChange: (value: AnalyticsPeriod) => void; grains?: string[];
}) {
  return <div className="my-4 flex flex-wrap gap-3">
    <label className="grid gap-1 text-sm">Start<input className="desk-input" type="date" value={value.start} max={value.end || undefined} onChange={event => onChange({ ...value, start: event.target.value })} /></label>
    <label className="grid gap-1 text-sm">End<input className="desk-input" type="date" value={value.end} min={value.start || undefined} onChange={event => onChange({ ...value, end: event.target.value })} /></label>
    {grains.length ? <label className="grid gap-1 text-sm">Grain<select className="desk-input" value={grains.includes(value.grain) ? value.grain : grains[0]} onChange={event => onChange({ ...value, grain: event.target.value })}>
      {grains.map(grain => <option key={grain} value={grain}>{grain}</option>)}
    </select></label> : null}
  </div>;
}
