import { t } from "@lingui/core/macro";
import { useDeferredValue, useMemo, useRef, useState } from "react";
import { PagePager } from "../../../components/ui/PagePager";
import type { Makerspace } from "../../../types/inventory";
import { SpaceCard, SpaceCardSkeletons } from "./SpaceCard";
import { SpacesEmpty, SpacesError, SpacesNoResults } from "./SpacesStates";
import { SpacesFilters, SpacesSearchBar } from "./SpacesToolbar";
import { filterSpaces, pageOf, placesOf, type SpacesSort } from "./spacesFilter";

export type SpacesQueryState = {
  spaces?: Makerspace[]; loading: boolean; error: boolean; retrying?: boolean; onRetry: () => void; hosting: boolean;
};

/** One or two spaces get the wide feature card; three or more share the responsive grid. */
export function SpacesCards({ spaces, headingLevel = 3 }: { spaces: Makerspace[]; headingLevel?: 2 | 3 }) {
  const feature = spaces.length <= 2;
  return <ul className={feature ? "sw-spaces-feature" : "sw-spaces-grid"} data-count={spaces.length}>
    {spaces.map(space => <li key={space.slug} className="flex min-w-0">
      <SpaceCard space={space} layout={feature ? "feature" : "grid"} headingLevel={headingLevel} />
    </li>)}
  </ul>;
}

/** The full directory: sticky search, place filter, sort, count, cards, pager and every state in the grid's place. */
export function SpacesDirectory({ spaces, loading, error, retrying, onRetry, hosting }: SpacesQueryState) {
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState("");
  const [sort, setSort] = useState<SpacesSort>("name");
  const [requestedPage, setRequestedPage] = useState(1);
  const top = useRef<HTMLElement>(null);
  const deferredQuery = useDeferredValue(query);
  const all = useMemo(() => spaces ?? [], [spaces]);
  const places = useMemo(() => placesOf(all), [all]);
  const results = useMemo(() => filterSpaces(all, { query: deferredQuery, place, sort }), [all, deferredQuery, place, sort]);
  const { page, items } = pageOf(results, requestedPage);
  const filtered = Boolean(query.trim() || place);
  const reset = (apply: () => void) => { apply(); setRequestedPage(1); };
  const clear = () => reset(() => { setQuery(""); setPlace(""); });
  const turnPage = (next: number) => { setRequestedPage(next); top.current?.scrollIntoView?.({ block: "start" }); };

  let body;
  if (error && !all.length) body = <SpacesError onRetry={onRetry} retrying={retrying} />;
  else if (loading) body = <SpaceCardSkeletons />;
  else if (!all.length) body = <SpacesEmpty hosting={hosting} />;
  else if (!results.length) body = <SpacesNoResults query={query} onClear={clear} />;
  else body = <>
    <SpacesCards spaces={items} />
    <div className="mt-8"><PagePager page={page} setPage={turnPage} count={results.length} /></div>
  </>;

  return <section ref={top} aria-labelledby="spaces-directory-title" className="sw-spaces-directory">
    <h2 id="spaces-directory-title" className="sr-only">{t`All spaces`}</h2>
    {loading || all.length > 1 ? <SpacesSearchBar query={query} onQuery={value => reset(() => setQuery(value))} /> : null}
    {all.length > 1 ? <SpacesFilters places={places} place={place} onPlace={value => reset(() => setPlace(value))} sort={sort}
      onSort={value => reset(() => setSort(value))} shown={results.length} total={all.length} filtered={filtered} onClear={clear} />
      : loading ? <div className="sw-spaces-filters" aria-hidden="true" /> : null}
    {body}
  </section>;
}
