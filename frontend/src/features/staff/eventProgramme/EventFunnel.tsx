import { Card } from "../../../components/ui";
export type Funnel = {
  event_id: number; timezone_name: string;
  // AN-c1: `application_stage` rows (one per live review stage, by `stage_position`) sit between responded and going.
  stages: { key: string; label: string; count: number; denominator: number; percent: number | null; stage_position?: number | null }[];
  timeline: { date: string; count: number; previous_count: number }[];
  capacity: { limit: number | null; going: number; remaining: number | null; state: string };
  caveat: string; reading: string; hint: string;
};
export function EventFunnel({ data }: { data: Funnel }) {
  return <Card><section className="grid gap-4" aria-label="Event participation funnel"><h4 className="font-semibold">From interest to feedback</h4>
    <ol className="grid gap-4 sm:grid-cols-4">{data.stages.map(stage => <li key={`${stage.key}-${stage.stage_position ?? ""}`} className="grid gap-2"><span className="text-sm text-muted">{stage.key === "application_stage" ? `Stage ${stage.stage_position}: ${stage.label}` : stage.label}</span><span className="text-2xl font-semibold tabular-nums">{stage.count}</span><progress className="h-3 w-full accent-brand" max={100} value={Math.max(0, Math.min(100, stage.percent ?? 0))} aria-label={`${stage.label} share`} /><span className="text-xs text-muted">{stage.denominator ? `${stage.count} of ${stage.denominator} · ${Math.round(stage.percent ?? 0)}%` : "No denominator yet"}</span></li>)}</ol>
    <p className="text-sm">{data.reading}</p><p className="text-sm text-muted">{data.caveat}</p><p className="rounded-xl border border-line bg-surface p-3 text-sm">{data.hint}</p>
    <p className="text-sm">Capacity: {data.capacity.state.replace(/_/g, " ")}{data.capacity.limit !== null ? ` · ${data.capacity.going} of ${data.capacity.limit} going` : " · no limit"}.</p>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-2 text-left font-semibold">14-day signups · {data.timezone_name}</caption><thead><tr><th scope="col" className="p-2">Day</th><th scope="col" className="p-2">Signups</th><th scope="col" className="p-2">Prior comparable day</th></tr></thead><tbody>{data.timeline.map(day => <tr key={day.date}><th className="p-2 font-normal" scope="row">{day.date}</th><td className="p-2 tabular-nums">{day.count}</td><td className="p-2 tabular-nums">{day.previous_count}</td></tr>)}</tbody></table></div>
  </section></Card>;
}
