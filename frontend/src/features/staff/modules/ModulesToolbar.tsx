import { t } from "@lingui/core/macro";
import { FilterBar, SegmentedControl } from "../../../components/ui";
import type { StateFilter } from "./moduleModel";

export type ViewMode = "area" | "role";
const chipClass = (on: boolean) => `min-h-11 rounded-full border px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${on ? "border-outline bg-panel text-ink" : "border-line text-muted hover:text-ink"}`;

export function ModulesToolbar({ view, onView, query, onQuery, filter, onFilter, counts }: {
  view: ViewMode; onView: (view: ViewMode) => void; query: string; onQuery: (query: string) => void;
  filter: StateFilter; onFilter: (filter: StateFilter) => void; counts: Record<StateFilter, number>;
}) {
  const chips: [StateFilter, string][] = [["all", t`All`], ["on", t`On`], ["off", t`Off`], ["locked", t`Locked`], ["changed", t`Changed here`]];
  return <div className="grid min-w-0 gap-3">
    <SegmentedControl label={t`Group switches`} value={view} onChange={value => onView(value as ViewMode)}
      options={[{ value: "area", label: t`By area` }, { value: "role", label: t`By role` }]} />
    <FilterBar value={query} onChange={onQuery} searchLabel={t`Search areas and features`} placeholder={t`Search areas, features or keys`} />
    <div role="group" aria-label={t`Filter by state`} className="flex flex-wrap gap-2">
      {chips.map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} className={chipClass(filter === value)} onClick={() => onFilter(value)}>
        {label} <span className="text-muted">{counts[value]}</span></button>)}
    </div>
  </div>;
}
