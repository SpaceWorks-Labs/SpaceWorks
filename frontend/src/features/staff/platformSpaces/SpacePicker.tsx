import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { healthKey, listSpaceHealth } from "./spacesApi";

export type PickedSpaces = Record<number, string>;

/** A searchable multi-select over the same space list the Health section reads. */
export function SpacePicker({ value, onChange }: { value: PickedSpaces; onChange: (next: PickedSpaces) => void }) {
  const [search, setSearch] = useState("");
  const term = useDebouncedValue(search.trim(), 300);
  const spaces = useQuery({ queryKey: [...healthKey, "", term, 1], queryFn: () => listSpaceHealth({ search: term, page: 1 }) });
  const toggle = (id: number, name: string) => {
    const next = { ...value };
    if (next[id]) delete next[id]; else next[id] = name;
    onChange(next);
  };
  const picked = Object.entries(value);
  return <fieldset className="grid gap-2 rounded-xl border border-line p-3">
    <legend className="px-1 text-sm font-semibold text-ink">{t`Spaces`}</legend>
    <p className="text-sm text-muted">{picked.length ? t`Selected: ${picked.map(([, name]) => name).join(", ")}` : t`No spaces selected yet.`}</p>
    <Field label={t`Find a space`}>
      <input className="desk-input" type="search" value={search} onChange={event => setSearch(event.target.value)} />
    </Field>
    <div className="grid max-h-56 gap-1 overflow-y-auto">
      {spaces.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading spaces…`}</p> : null}
      {spaces.isError ? <p role="alert" className="text-sm text-danger">{t`Couldn't load spaces.`}</p> : null}
      {(spaces.data?.results ?? []).map(space => <label key={space.id} className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="checkbox" checked={Boolean(value[space.id])} onChange={() => toggle(space.id, space.name)} />{space.name}
      </label>)}
    </div>
  </fieldset>;
}
