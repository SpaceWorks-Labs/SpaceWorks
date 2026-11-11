import { t } from "@lingui/core/macro";
import { useState } from "react";
import { CollapsibleSection } from "../../../../components/ui";
import { AttentionRow } from "./WaitingOnMe";
import { areaLabel, type Attention, type AttentionRouting } from "./attention";

/**
 * Decision 242(j): one collapsible section per area the viewer runs, each with its total, and an area
 * filter. The server builds `areas` from the viewer's own actions, so an area manager sees only theirs.
 * An area whose counters failed is listed as "couldn't load", never as a silent 0 (U13).
 */
export function AreaSections({ attention, routing }: { attention: Attention; routing: AttentionRouting }) {
  const keys = [...attention.areas.map(area => area.key), ...attention.errors.filter(key => !attention.areas.some(area => area.key === key))];
  const [filter, setFilter] = useState("");
  const [closed, setClosed] = useState<Set<string>>(() => new Set(attention.areas.filter(area => area.total === 0).map(area => area.key)));
  if (!keys.length) return null;
  const shown = filter ? keys.filter(key => key === filter) : keys;
  const toggle = (key: string) => setClosed(current => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  return <section aria-labelledby="dashboard-by-area" className="grid gap-3">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <h2 id="dashboard-by-area" className="title-panel">{t`By area`}</h2>
      {keys.length > 1 ? <label className="grid gap-1 text-sm">{t`Show area`}
        <select className="desk-input min-h-11" value={filter} onChange={event => setFilter(event.target.value)}>
          <option value="">{t`All areas`}</option>
          {keys.map(key => <option key={key} value={key}>{areaLabel(key)}</option>)}
        </select>
      </label> : null}
    </div>
    <div className="grid gap-3">
      {shown.map(key => {
        const area = attention.areas.find(row => row.key === key);
        if (!area) return <div key={key} role="alert" className="rounded-xl border border-line bg-panel px-4 py-3 text-sm">
          <span className="font-semibold">{areaLabel(key)}</span>{" · "}{t`Couldn't load this area's numbers.`}</div>;
        return <CollapsibleSection key={key} title={`${areaLabel(key)} · ${t`Total`} ${area.total}`} open={!closed.has(key)} onToggle={() => toggle(key)}>
          <ul className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-3">
            {area.items.map(item => <li key={item.key}><AttentionRow item={item} routing={routing} /></li>)}
          </ul>
        </CollapsibleSection>;
      })}
    </div>
  </section>;
}
