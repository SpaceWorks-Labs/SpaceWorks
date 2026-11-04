import { SegmentedControl } from "../../components/ui";
import { currentMonth, useDiscoveryState } from "./useDiscoveryState";

export function DiscoveryControls({ state, searchLabel, filters }: {
  state: ReturnType<typeof useDiscoveryState>;
  searchLabel: string;
  filters: { value: string; label: string }[];
}) {
  return <div className="desk-panel mb-5 flex flex-wrap items-end gap-3 p-4">
    <label className="min-w-0 flex-1 basis-full text-sm font-semibold sm:basis-64">{searchLabel}
      <input type="search" className="desk-input mt-1 w-full" value={state.query} onChange={(event) => state.update({ q: event.target.value })} />
    </label>
    <label className="min-w-0 flex-1 basis-40 text-sm font-semibold sm:flex-none">Filter
      <select className="desk-input mt-1 w-full" value={state.facet} onChange={(event) => state.update({ filter: event.target.value })}>
        <option value="">All</option>{filters.map((filter) => <option key={filter.value} value={filter.value}>{filter.label}</option>)}
      </select>
    </label>
    <label className="min-w-0 flex-1 basis-40 text-sm font-semibold sm:flex-none">Month
      <input type="month" min="1900-01" max="9998-12" className="desk-input mt-1 w-full" value={state.month} onChange={(event) => state.update({ month: event.target.value })} />
    </label>
    <div className="flex flex-wrap gap-2" role="group" aria-label="Discovery view">
      <SegmentedControl label="Discovery view" value={state.view} options={[{ value: "agenda", label: "List" }, { value: "calendar", label: "Month calendar" }]} onChange={value => state.update(value === "calendar" ? { view: "calendar", month: state.month || currentMonth(state.timeZone) } : { view: "" })} />
      <button type="button" className="desk-button-ghost" onClick={() => state.update({ q: "", filter: "", month: "", view: "" })}>Clear filters</button>
    </div>
  </div>;
}
