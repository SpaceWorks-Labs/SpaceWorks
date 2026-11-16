import { plural, t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { FilterBar } from "../../../components/ui";
import { ListSort } from "../../../components/layouts/ListSort";
import type { SpacesSort } from "./spacesFilter";

/** The search row sticks to the top of the viewport (phones included); a sentinel adds its edge once stuck. */
export function SpacesSearchBar({ query, onQuery }: { query: string; onQuery: (value: string) => void }) {
  const sentinel = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting), { rootMargin: "-73px 0px 0px 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return <>
    <div ref={sentinel} aria-hidden="true" className="h-px" />
    <form role="search" className="sw-spaces-search" data-stuck={stuck || undefined} onSubmit={event => event.preventDefault()}>
      <FilterBar value={query} onChange={onQuery} searchLabel={t`Search spaces`} placeholder={t`Search by name, code or place`} />
    </form>
  </>;
}

/** Place filter, sort, the live result count and the way back to everything. */
export function SpacesFilters({ places, place, onPlace, sort, onSort, shown, total, filtered, onClear }: {
  places: string[]; place: string; onPlace: (value: string) => void; sort: SpacesSort; onSort: (value: SpacesSort) => void;
  shown: number; total: number; filtered: boolean; onClear: () => void;
}) {
  const count = filtered ? plural(total, { one: `${shown} of # space`, other: `${shown} of # spaces` })
    : plural(total, { one: "# space", other: "# spaces" });
  return <div className="sw-spaces-filters">
    <p className="sw-spaces-count" aria-live="polite">{count}</p>
    <div className="sw-spaces-filter-controls">
      {filtered ? <button type="button" className="desk-button-ghost" onClick={onClear}>{t`Clear filters`}</button> : null}
      {places.length > 1 ? <label className="relative flex h-11 min-w-0 items-center">
        <span aria-hidden="true" className="pointer-events-none absolute left-3 text-sm text-muted">{t`Place:`}</span>
        <span className="sr-only">{t`Filter by place`}</span>
        <select className="desk-input h-11 w-full min-w-0 pl-[3.75rem] sm:w-56" value={place} onChange={event => onPlace(event.target.value)}>
          <option value="">{t`All places`}</option>
          {places.map(name => <option key={name} value={name}>{name}</option>)}
        </select>
      </label> : null}
      <ListSort value={sort} label={t`Sort spaces`} onChange={event => onSort(event.target.value === "-name" ? "-name" : "name")}
        options={[["name", t`Name A–Z`], ["-name", t`Name Z–A`]]} />
    </div>
  </div>;
}
