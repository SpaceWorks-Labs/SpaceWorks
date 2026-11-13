import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListRow } from "../../../components/ui";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { openSpaceTab } from "./openSpaceTab";
import { crossSpaceKeys, searchPlatform, type SearchHit } from "./crossSpaceApi";
import { SearchField } from "../../../components/ui/SearchField";

const KIND = (): Record<SearchHit["kind"], string> => ({ space: t`Space`, person: t`Person`, receipt: t`Receipt` });

/**
 * Decision 242(l) / U10: find a space, a person's account or a receipt number across every space.
 * The server returns only which space a hit belongs to; opening one goes to that space's own page.
 * Searches are audited without their text and rate-limited, so nothing is sent below 3 characters.
 */
export function PlatformSearch({ spaceNames }: { spaceNames: Record<number, string> }) {
  const id = useId();
  const [text, setText] = useState("");
  const term = useDebouncedValue(text, 400).trim();
  const ready = term.length >= 3 && term.length <= 100;
  const search = useQuery({ queryKey: crossSpaceKeys.search(term), enabled: ready, staleTime: 30_000, retry: false,
    queryFn: ({ signal }) => searchPlatform(term, signal) });
  const hits = ready ? search.data?.results ?? [] : [];
  const open = (spaceId: number, path: string) => openSpaceTab(spaceId, path);
  return <div className="grid gap-3">
    <label htmlFor={`${id}-q`} className="text-sm font-semibold">{t`Space name, person's username or email, or receipt number`}</label>
    <SearchField expand id={`${id}-q`} className="desk-input max-w-xl" maxLength={100} value={text} onChange={event => setText(event.target.value)}
      aria-describedby={`${id}-hint`} />
    <p id={`${id}-hint`} className="text-xs text-muted">{t`Type at least 3 characters. Results show which space a match belongs to, never its records.`}</p>
    <div role="status" aria-live="polite" className="text-sm text-muted">
      {ready && search.isFetching ? t`Searching…` : ready && search.isSuccess ? t`${hits.length} matches` : ""}
    </div>
    {ready && search.isError ? <p role="alert" className="text-sm text-danger">{t`Search didn't work: ${search.error.message}`}</p> : null}
    {ready && search.isSuccess && !hits.length ? <p className="text-sm text-muted">{t`No space, person or receipt matches that.`}</p> : null}
    {hits.length ? <ul className="grid gap-2">{hits.map((hit, index) => {
      const spaces = hit.kind === "person" ? hit.space_ids ?? [] : hit.space_id ? [hit.space_id] : [];
      const where = spaces.map(space => spaceNames[space] ?? t`Space #${space}`).join(", ");
      return <li key={`${hit.kind}:${hit.label}:${index}`}><ListRow title={hit.label}
        meta={`${KIND()[hit.kind]}${where ? ` · ${where}` : hit.kind === "person" ? ` · ${t`No staff or member role in a live space`}` : ""}`}
        right={spaces.length ? <div className="flex flex-wrap gap-2">{spaces.slice(0, 3).map(space => <button key={space} type="button" className="desk-button min-h-11"
          onClick={() => open(space, hit.kind === "receipt" ? `/admin/payments?search=${encodeURIComponent(hit.label)}` : hit.kind === "person" ? "/admin/members" : "/admin/dashboard")}>
          {t`Open in ${spaceNames[space] ?? t`space #${space}`}`}</button>)}</div> : undefined} /></li>;
    })}</ul> : null}
  </div>;
}
