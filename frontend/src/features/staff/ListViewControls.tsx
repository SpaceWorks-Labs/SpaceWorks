import type { ReactNode } from "react";
import { ListFilters, type ListFiltersProps } from "../../components/layouts/ListFilters";
import { ListSort } from "../../components/layouts/ListSort";
import type { UrlListState } from "../../lib/useUrlListState";
import { SavedViewsMenu } from "./SavedViewsMenu";

export function ListViewControls({ state, makerspaceId, entity, sorts, search = true, searchLabel = "Search", searchControl, controls, activeCount = 0 }: {
  state: UrlListState; makerspaceId: number; entity: string; sorts: readonly (readonly [string, string])[]; search?: boolean;
  searchLabel?: string; searchControl?: ListFiltersProps["search"]; controls?: ReactNode; activeCount?: number;
}) {
  return <ListFilters search={searchControl ?? (search ? { label: searchLabel, value: state.values.q ?? "", onChange: value => state.setFilter("q", value) } : undefined)}
    sort={<ListSort value={state.values.ordering} onChange={event => state.setFilter("ordering", event.target.value)} options={sorts} />}
    views={<SavedViewsMenu makerspaceId={makerspaceId} entity={entity} state={state.values} onRestore={state.restore} />}
    controls={controls} activeCount={activeCount}
    chips={state.values.id ? [{ key: "id", label: "Selected result", onRemove: () => state.setFilter("id", "") }] : []} />;
}
