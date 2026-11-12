import { t } from "@lingui/core/macro";

import type { MaintenanceSpec } from "./templatesApi";

const TRIGGERS = (): [MaintenanceSpec["trigger"], string][] => [["days", t`Days`], ["usage_hours", t`Machine hours`], ["job_count", t`Jobs`]];

/** The template's maintenance checklist: a title, what the interval counts, and the interval. */
export function SpecMaintenance({ items, onChange }: { items: MaintenanceSpec[]; onChange: (next: MaintenanceSpec[]) => void }) {
  const patch = (index: number, change: Partial<MaintenanceSpec>) => onChange(items.map((item, at) => at === index ? { ...item, ...change } : item));
  return <div className="grid gap-2">
    {!items.length ? <p className="text-sm text-muted">{t`No maintenance items yet.`}</p> : null}
    {items.map((item, index) => <div key={index} className="grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-3">
      <label className="grid gap-1 text-sm sm:col-span-3">{t`Title`}<input className="desk-input" value={item.title} maxLength={200} onChange={event => patch(index, { title: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">{t`Counted in`}<select className="desk-input" value={item.trigger} onChange={event => patch(index, { trigger: event.target.value as MaintenanceSpec["trigger"] })}>
        {TRIGGERS().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="grid gap-1 text-sm">{t`Every`}<input className="desk-input tabular-nums" inputMode="numeric" aria-label={t`Interval for maintenance item ${index + 1}`} value={Number.isNaN(item.interval) ? "" : item.interval}
        onChange={event => patch(index, { interval: Number(event.target.value) })} /></label>
      <div className="flex items-end"><button type="button" className="desk-button-danger min-h-11" onClick={() => onChange(items.filter((_, at) => at !== index))}>{t`Remove item`}</button></div>
    </div>)}
    <div><button type="button" className="desk-button min-h-11" onClick={() => onChange([...items, { title: "", trigger: "days", interval: 30 }])}>{t`Add a maintenance item`}</button></div>
  </div>;
}
