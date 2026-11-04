import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { financeError } from "../../finance/financeApi";
import { sponsorApi, sponsorKeys, type Perk } from "./staffSponsorsApi";

function PerkRow({ makerspaceId, perk, canRecord }: { makerspaceId: number; perk: Perk; canRecord: boolean }) {
  const client = useQueryClient();
  const tick = useMutation({
    mutationFn: (fulfilled: boolean) => sponsorApi.fulfil(makerspaceId, perk.id, fulfilled),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["staff-sponsor-perks", makerspaceId] }),
  });
  const overdue = !perk.fulfilled_at && perk.due_on && new Date(perk.due_on) < new Date();
  return <li className="flex min-h-11 flex-wrap items-center gap-3 border-b border-line py-2 text-sm last:border-0">
    <label className="flex min-h-11 flex-1 items-center gap-2">
      <input type="checkbox" checked={Boolean(perk.fulfilled_at)} disabled={!canRecord || tick.isPending}
        onChange={event => tick.mutate(event.target.checked)} />
      <span className={perk.fulfilled_at ? "text-muted line-through" : "text-ink"}>{perk.description}</span>
    </label>
    <span className={`text-xs ${overdue ? "text-danger" : "text-muted"}`}>
      {perk.fulfilled_at ? `Done ${new Date(perk.fulfilled_at).toLocaleDateString()}${perk.fulfilled_by_name ? ` by ${perk.fulfilled_by_name}` : ""}`
        : perk.due_on ? `${overdue ? "Overdue since" : "Due"} ${new Date(perk.due_on).toLocaleDateString()}` : "No due date"}</span>
    {tick.error ? <span role="alert" className="text-xs text-danger">{financeError(tick.error)}</span> : null}
  </li>;
}

/** A sponsor's perk checklist: copies of its tier's perks plus its own, each ticked off by staff. */
export function SponsorPerks({ makerspaceId, sponsorId, canRecord }: { makerspaceId: number; sponsorId: number; canRecord: boolean }) {
  const client = useQueryClient();
  const perks = useQuery({ queryKey: sponsorKeys.perks(makerspaceId, sponsorId), queryFn: () => sponsorApi.perks(makerspaceId, sponsorId) });
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const add = useMutation({
    mutationFn: () => sponsorApi.createPerk(makerspaceId, { sponsor: sponsorId, description, due_on: due || null }),
    onSuccess: () => { setDescription(""); setDue(""); void client.invalidateQueries({ queryKey: ["staff-sponsor-perks", makerspaceId] }); },
  });
  return <section className="grid gap-3" aria-label="Perks">
    <h3 className="title-section">Perks</h3>
    {perks.data?.length ? <ul>{perks.data.map(perk => <PerkRow key={perk.id} makerspaceId={makerspaceId} perk={perk}
      canRecord={canRecord} />)}</ul> : <p className="text-sm text-muted">No perks yet.</p>}
    {canRecord ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); add.mutate(); }}>
      <label className="grid flex-1 gap-1 text-sm font-semibold text-ink">New perk<input className="desk-input" required maxLength={300}
        value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">Due<input className="desk-input" type="date" value={due}
        onChange={event => setDue(event.target.value)} /></label>
      <button type="submit" className="desk-button" disabled={add.isPending}>Add</button>
    </form> : null}
    {add.error ? <p role="alert" className="text-sm text-danger">{financeError(add.error)}</p> : null}
  </section>;
}
