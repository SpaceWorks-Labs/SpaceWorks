import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, ErrorText } from "../../../components/ui";
import { useStaffCommand, useStaffQuery, type CheckInList } from "./api";
import { CheckInListRow } from "./CheckInListRow";

/** Open lists in desk order, then archived ones (the server returns them oldest first). */
export function orderLists(rows: CheckInList[]) {
  const open = rows.filter(row => !row.archived).sort((a, b) => (a.position ?? 0) - (b.position ?? 0) || a.id - b.id);
  return [...open, ...rows.filter(row => row.archived)];
}

/**
 * Extra check-in lists (X45): swag, a meal, a workshop. Collecting from a list never changes entry check-in.
 * Online only; an archived list is read-only until it is restored. Staff who manage registrations set the desk
 * order (parity E-B5, D22).
 */
export function CheckInListsPanel({ eventId, canManage, addons }: {
  eventId: number; canManage: boolean; addons: { id: number; name: string }[];
}) {
  const lists = useStaffQuery<CheckInList[]>(eventId, "/checkin-lists/");
  const command = useStaffCommand<CheckInList>(eventId), reorder = useStaffCommand<CheckInList[]>(eventId);
  const [name, setName] = useState(""), [kind, setKind] = useState("swag"), [afterEntry, setAfterEntry] = useState(false);
  const [addon, setAddon] = useState("");
  const rows = orderLists(lists.data ?? []);
  const open = rows.filter(row => !row.archived);
  const error = lists.error ?? command.error ?? reorder.error;
  const move = (index: number, direction: -1 | 1) => {
    const ids = open.map(row => row.id);
    [ids[index], ids[index + direction]] = [ids[index + direction], ids[index]];
    reorder.mutate({ suffix: "/checkin-lists/reorder/", body: { ordered_ids: ids } });
  };
  return <section className="grid gap-4" aria-labelledby="lists-heading">
    <header className="grid gap-1">
      <h3 id="lists-heading" className="text-lg font-semibold text-ink">{t`Check-in lists`}</h3>
      <p className="text-sm text-muted">{t`Track swag, meals or a workshop separately from entry. Online only.`}</p>
    </header>
    {error ? <ErrorText message={error.message} /> : null}
    {lists.data?.length === 0 ? <p className="text-sm text-muted">{t`No lists yet.`}</p> : null}
    <ul className="grid gap-2">{rows.map(list => {
      const index = open.findIndex(row => row.id === list.id);
      return <CheckInListRow key={list.id} eventId={eventId} list={list} canManage={canManage} moving={reorder.isPending}
        first={index <= 0} last={index === open.length - 1} onMove={direction => move(index, direction)} />;
    })}</ul>
    {canManage ? <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault();
      command.mutate({ suffix: "/checkin-lists/", body: { name, kind, after_entry: afterEntry, ...(addon ? { addon_id: Number(addon) } : {}) } },
        { onSuccess: () => setName("") }); }}>
      <p className="font-semibold text-ink">{t`New list`}</p>
      <label className="grid gap-1 text-sm text-ink">{t`Name`}<input className="desk-input" required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
      <label className="grid gap-1 text-sm text-ink">{t`Kind`}<select className="desk-input" value={kind} onChange={e => setKind(e.target.value)}>
        <option value="swag">{t`Swag`}</option><option value="meal">{t`Meal`}</option><option value="workshop">{t`Workshop`}</option><option value="other">{t`Other`}</option></select></label>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={afterEntry}
        onChange={e => setAfterEntry(e.target.checked)} />{t`Only after entry check-in`}</label>
      {addons.length ? <label className="grid gap-1 text-sm text-ink">{t`Only for buyers of an add-on`}<select className="desk-input" value={addon} onChange={e => setAddon(e.target.value)}><option value="">{t`Everyone with a place`}</option>
          {addons.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : null}
      <button type="submit" className="desk-button justify-self-start" disabled={!name.trim() || command.isPending}>{t`Create list`}</button>
    </form></Card> : null}
  </section>;
}
