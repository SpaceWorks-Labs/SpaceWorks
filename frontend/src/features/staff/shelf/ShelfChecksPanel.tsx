import { t } from "@lingui/core/macro";
import { useDeferredValue, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../components/BoxSpinner";
import { LogoLoader } from "../../../components/LogoLoader";
import { Callout, Field, StatusPill } from "../../../components/ui";
import { adapterErrorMessage } from "../panels/machine/adapters/adapterCopy";
import { ShelfCheckHistory } from "./ShelfCheckHistory";
import { ShowOnShelf } from "./ShowOnShelf";
import { shelfApi, shelfKeys, type ShelfCheckEntry } from "./shelfApi";

type Mark = { status: "ok" | "attention"; note: string };

/** "Check shelves": walk the storage locations, mark each OK or Needs attention (with a note) and save the walk as one record. */
export function ShelfChecksPanel({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [prefix, setPrefix] = useState("");
  const [marks, setMarks] = useState<Record<string, Mark>>({});
  const filter = useDeferredValue(prefix.trim());
  const locations = useQuery({ queryKey: shelfKeys.locations(makerspaceId, filter), queryFn: () => shelfApi.locations(makerspaceId, filter), retry: false });
  const save = useMutation({
    mutationFn: () => shelfApi.saveCheck(makerspaceId, { scope_label: filter, entries: Object.entries(marks).map(([location, mark]): ShelfCheckEntry => ({ location, ...mark })) }),
    onSuccess: () => { setMarks({}); void client.invalidateQueries({ queryKey: shelfKeys.checks(makerspaceId) }); },
  });
  const marked = Object.keys(marks).length;
  const mark = (location: string, next: Mark | null) => setMarks(current => { const { [location]: _gone, ...rest } = current; return next ? { ...rest, [location]: next } : rest; });
  const rows = locations.data ?? [];
  return <div className="grid gap-4">
    <Callout size="inline" tone="warn" lead={t`Staff only.`} body={t`Walk the shelves, mark what you see, then save. The pointer can light each shelf for you where one is set up.`} />
    <Field label={t`Only shelves starting with`}><input className="desk-input" value={prefix} onChange={event => setPrefix(event.target.value)} placeholder={t`e.g. Shelf B`} /></Field>
    {locations.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
    {locations.error ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(locations.error)}</p> : null}
    {!locations.isLoading && !locations.error && !rows.length ? <p className="text-sm text-muted">{t`No storage locations match. Give items a storage location first.`}</p> : null}
    <ul className="grid gap-2">{rows.map(row => { const current = marks[row.location];
      return <li key={row.location} className="grid gap-2 rounded-md border border-line p-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><div className="min-w-0"><strong className="text-ink [overflow-wrap:anywhere]">{row.location}</strong>
          <span className="ms-2 text-xs text-muted">{t`${row.item_count} items`}</span></div>
          {current ? <StatusPill tone={current.status === "ok" ? "success" : "warn"} label={current.status === "ok" ? t`OK` : t`Needs attention`} /> : null}</div>
        <ShowOnShelf makerspaceId={makerspaceId} targetType="storage_location" targetId={row.location} covered={row.covered} />
        <div className="flex flex-wrap gap-2" role="group" aria-label={t`Finding for ${row.location}`}>
          <button type="button" className={current?.status === "ok" ? "desk-button-primary" : "desk-button"} aria-pressed={current?.status === "ok"} onClick={() => mark(row.location, current?.status === "ok" ? null : { status: "ok", note: "" })}>{t`OK`}</button>
          <button type="button" className={current?.status === "attention" ? "desk-button-primary" : "desk-button"} aria-pressed={current?.status === "attention"} onClick={() => mark(row.location, current?.status === "attention" ? null : { status: "attention", note: current?.note ?? "" })}>{t`Needs attention`}</button></div>
        {current?.status === "attention" ? <input className="desk-input" maxLength={200} aria-label={t`Note for ${row.location}`} placeholder={t`What needs attention?`} value={current.note} onChange={event => mark(row.location, { status: "attention", note: event.target.value })} /> : null}
      </li>; })}</ul>
    {save.error ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(save.error)}</p> : null}
    {save.isSuccess && !marked ? <p role="status" className="text-sm text-muted">{t`Shelf check saved.`}</p> : null}
    <button type="button" className="desk-button-primary justify-self-start" disabled={!marked || save.isPending} onClick={() => save.mutate()}>
      {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save shelf check (${marked} marked)`}</button>
    <ShelfCheckHistory makerspaceId={makerspaceId} />
  </div>;
}
