import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { healthKey, listSpaceHealth } from "../platformSpaces/spacesApi";

export type PickedSpace = { id: number; name: string };

/** Search, then choose one space, from the same list the Spaces page reads. */
export function SingleSpaceSelect({ value, onChange }: { value: PickedSpace | null; onChange: (next: PickedSpace | null) => void }) {
  const [search, setSearch] = useState("");
  const term = useDebouncedValue(search.trim(), 300);
  const spaces = useQuery({ queryKey: [...healthKey, "", term, 1], queryFn: () => listSpaceHealth({ search: term, page: 1 }) });
  const options = spaces.data?.results ?? [];
  return <div className="grid gap-4 sm:grid-cols-2">
    <Field label={t`Find a space`}>
      <input className="desk-input" type="search" value={search} onChange={event => setSearch(event.target.value)} />
    </Field>
    <Field label={t`Space`} hint={spaces.isError ? t`Couldn't load spaces.` : spaces.isLoading ? t`Loading spaces…` : undefined}>
      <select className="desk-input" value={value?.id ?? ""} onChange={event => {
        const space = options.find(option => option.id === Number(event.target.value));
        onChange(space ? { id: space.id, name: space.name } : null);
      }}>
        <option value="">{t`Choose a space`}</option>
        {value && !options.some(option => option.id === value.id) ? <option value={value.id}>{value.name}</option> : null}
        {options.map(space => <option key={space.id} value={space.id}>{space.name}</option>)}
      </select>
    </Field>
  </div>;
}
