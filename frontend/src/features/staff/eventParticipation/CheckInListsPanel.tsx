import { useState } from "react";
import { Card, ErrorText, StatusBadge } from "../../../components/ui";
import { useStaffCommand, useStaffQuery, type CheckInList, type ListEligibility } from "./api";

const REASONS: Record<string, string> = {
  not_confirmed: "No confirmed place.", entry_required: "Check them in at the door first.",
  not_eligible: "Did not buy this add-on.", already_collected: "Already collected everything.",
};

/**
 * Extra check-in lists (X45): swag, a meal, a workshop. Collecting from a list never changes
 * entry check-in. Online only; an archived list is read-only.
 */
export function CheckInListsPanel({ eventId, canManage, addons }: {
  eventId: number; canManage: boolean; addons: { id: number; name: string }[];
}) {
  const lists = useStaffQuery<CheckInList[]>(eventId, "/checkin-lists/");
  const command = useStaffCommand<CheckInList>(eventId), scan = useStaffCommand<ListEligibility>(eventId);
  const [name, setName] = useState(""), [kind, setKind] = useState("swag"), [afterEntry, setAfterEntry] = useState(false);
  const [addon, setAddon] = useState(""), [active, setActive] = useState<number | null>(null), [registration, setRegistration] = useState("");
  const [result, setResult] = useState<ListEligibility | null>(null);
  const error = lists.error ?? command.error;
  const collect = (listId: number) => scan.mutate({ suffix: `/checkin-lists/${listId}/scan/`, body: {
    operation_id: crypto.randomUUID(), registration_id: Number(registration) } }, { onSuccess: setResult });
  return <section className="grid gap-4" aria-labelledby="lists-heading">
    <header className="grid gap-1">
      <h3 id="lists-heading" className="text-lg font-semibold text-ink">Check-in lists</h3>
      <p className="text-sm text-muted">Track swag, meals or a workshop separately from entry. Online only.</p>
    </header>
    {error ? <ErrorText message={error.message} /> : null}
    {lists.data?.length === 0 ? <p className="text-sm text-muted">No lists yet.</p> : null}
    <ul className="grid gap-2">{lists.data?.map(list => <li key={list.id}><Card><div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="font-semibold text-ink">{list.name}</p>
          <p className="text-sm text-muted">{list.collected} collected{list.after_entry ? " · after entry" : ""}
            {list.addon_name ? ` · buyers of ${list.addon_name}` : ` · ${list.per_person} per person`}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          {list.archived ? <StatusBadge status="archived" label="Archived, read-only" /> : <>
            <button type="button" className="desk-button" aria-expanded={active === list.id}
              onClick={() => { setActive(active === list.id ? null : list.id); setResult(null); }}>Collect</button>
            {canManage ? <button type="button" className="desk-button" disabled={command.isPending}
              onClick={() => command.mutate({ suffix: `/checkin-lists/${list.id}/`, method: "PATCH", body: { archive: true } })}>Archive</button> : null}
          </>}
        </div>
      </div>
      {active === list.id ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); collect(list.id); }}>
        <label className="grid gap-1 text-sm text-ink">Registration number
          <input className="desk-input" inputMode="numeric" required value={registration}
            onChange={e => setRegistration(e.target.value.replace(/\D/g, ""))} /></label>
        <button type="submit" className="desk-button" disabled={!registration || scan.isPending}>Record collection</button>
        <div role="status" aria-live="polite" className="text-sm">
          {result ? <span className="text-ink">{result.name}: {result.used} of {result.allowed} collected.</span> : null}
          {scan.error ? <span className="text-danger">{REASONS[(scan.error as { code?: string }).code ?? ""] ?? scan.error.message}</span> : null}
        </div>
      </form> : null}
    </div></Card></li>)}</ul>
    {canManage ? <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault();
      command.mutate({ suffix: "/checkin-lists/", body: { name, kind, after_entry: afterEntry, ...(addon ? { addon_id: Number(addon) } : {}) } },
        { onSuccess: () => setName("") }); }}>
      <p className="font-semibold text-ink">New list</p>
      <label className="grid gap-1 text-sm text-ink">Name<input className="desk-input" required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
      <label className="grid gap-1 text-sm text-ink">Kind<select className="desk-input" value={kind} onChange={e => setKind(e.target.value)}>
        <option value="swag">Swag</option><option value="meal">Meal</option><option value="workshop">Workshop</option><option value="other">Other</option></select></label>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={afterEntry}
        onChange={e => setAfterEntry(e.target.checked)} />Only after entry check-in</label>
      {addons.length ? <label className="grid gap-1 text-sm text-ink">Only for buyers of an add-on
        <select className="desk-input" value={addon} onChange={e => setAddon(e.target.value)}><option value="">Everyone with a place</option>
          {addons.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : null}
      <button type="submit" className="desk-button justify-self-start" disabled={!name.trim() || command.isPending}>Create list</button>
    </form></Card> : null}
  </section>;
}
