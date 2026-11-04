import { type ReactNode } from "react";
import { ActionControl, FilterBar } from "../ui";
import { FilterPopover } from "./FilterPopover";

export type ListFiltersProps = {
  search?: { label: string; value: string; onChange: (value: string) => void; placeholder?: string };
  sort?: ReactNode;
  views?: ReactNode;
  controls?: ReactNode;
  activeCount?: number;
  toolbar?: ReactNode;
  chips?: { key: string; label: string; onRemove: () => void }[];
  onClear?: () => void;
};

/** The toolbar owns presentation; callers retain URL state and query behaviour. */
export function ListFilters({ search, sort, views, controls, activeCount, toolbar, chips = [], onClear }: ListFiltersProps) {
  if (toolbar) return toolbar;
  return <div className="grid min-w-0 gap-3">
    <div className="flex min-w-0 flex-wrap items-center gap-3">
      {search ? <div className="min-w-0 flex-1 basis-full sm:basis-48"><FilterBar value={search.value} onChange={search.onChange}
        searchLabel={search.label} placeholder={search.placeholder ?? search.label} /></div> : null}
      <div className="flex min-w-0 flex-wrap items-center gap-2 [&_.desk-input]:h-11 [&_.desk-button]:h-11">
        {sort}
        {controls ? <FilterPopover count={activeCount ?? chips.length} onClear={onClear}>{controls}</FilterPopover> : null}
        {views}
      </div>
    </div>
    {chips.length ? <div className="flex flex-wrap items-center gap-2">
      {chips.map(chip => <ActionControl key={chip.key} action={{ label: `Remove ${chip.label}`, onClick: chip.onRemove }} />)}
      {onClear ? <ActionControl action={{ label: "Clear filters", onClick: onClear }} /> : null}
    </div> : null}
  </div>;
}
