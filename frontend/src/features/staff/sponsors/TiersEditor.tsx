import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, EmptyState } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { sponsorApi, sponsorKeys, type Tier } from "./staffSponsorsApi";

function TierPerks({ makerspaceId, tier, perks, canRecord }: {
  makerspaceId: number; tier: Tier; perks: { id: number; description: string; due_on: string | null }[]; canRecord: boolean;
}) {
  const client = useQueryClient();
  const [description, setDescription] = useState("");
  const add = useMutation({ mutationFn: () => sponsorApi.createPerk(makerspaceId, { tier: tier.id, description, due_on: null }),
    onSuccess: () => { setDescription(""); void client.invalidateQueries({ queryKey: ["staff-sponsor-perks", makerspaceId] }); } });
  return <Card><div className="grid gap-3">
    <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="title-section">{tier.name}</h3>
      {tier.amount ? <span className="text-sm tabular-nums text-muted">{tier.currency.toUpperCase()} {tier.amount}</span> : null}</div>
    {tier.description ? <p className="text-sm text-muted">{tier.description}</p> : null}
    {perks.length ? <ul className="list-disc pl-5 text-sm">{perks.map(perk => <li key={perk.id}>{perk.description}</li>)}</ul>
      : <p className="text-sm text-muted">No perks in this tier yet.</p>}
    {canRecord ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); add.mutate(); }}>
      <label className="grid flex-1 gap-1 text-sm font-semibold text-ink">Add a perk every {tier.name} sponsor gets
        <input className="desk-input" required maxLength={300} value={description} onChange={event => setDescription(event.target.value)} /></label>
      <button type="submit" className="desk-button" disabled={add.isPending}>Add</button></form> : null}
    {add.error ? <p role="alert" className="text-sm text-danger">{financeError(add.error)}</p> : null}
  </div></Card>;
}

/** Tiers group sponsors; a tier's perks are copied onto each of its sponsors as their own checklist. */
export function TiersEditor({ makerspaceId, canRecord }: { makerspaceId: number; canRecord: boolean }) {
  const client = useQueryClient();
  const tiers = useQuery({ queryKey: sponsorKeys.tiers(makerspaceId), queryFn: () => sponsorApi.tiers(makerspaceId) });
  const perks = useQuery({ queryKey: sponsorKeys.perks(makerspaceId, "all"), queryFn: () => sponsorApi.perks(makerspaceId, "all") });
  const [form, setForm] = useState({ name: "", rank: "0", amount: "", description: "" });
  const create = useMutation({
    mutationFn: () => sponsorApi.createTier(makerspaceId, { name: form.name, rank: Number(form.rank) || 0,
      amount: form.amount || null, description: form.description }),
    onSuccess: () => { setForm({ name: "", rank: "0", amount: "", description: "" });
      void client.invalidateQueries({ queryKey: sponsorKeys.tiers(makerspaceId) }); },
  });
  const templates = (tier: number) => (perks.data ?? []).filter(perk => perk.tier === tier && perk.sponsor === null);
  return <div className="grid gap-4">
    {tiers.error ? <p role="alert" className="text-sm text-danger">{financeError(tiers.error)}</p> : null}
    {tiers.data && !tiers.data.length ? <EmptyState message="No tiers yet. Tiers are optional." /> : null}
    {tiers.data?.map(tier => <TierPerks key={tier.id} makerspaceId={makerspaceId} tier={tier} perks={templates(tier.id)}
      canRecord={canRecord} />)}
    {canRecord ? <form className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end" aria-label="New tier"
      onSubmit={event => { event.preventDefault(); create.mutate(); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">New tier<input className="desk-input" required maxLength={80}
        value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">Order<input className="desk-input" type="number" min="0"
        value={form.rank} onChange={event => setForm({ ...form, rank: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">Suggested amount<input className="desk-input" inputMode="decimal"
        value={form.amount} onChange={event => setForm({ ...form, amount: event.target.value })} /></label>
      <button type="submit" className="desk-button" disabled={create.isPending}>Add tier</button>
    </form> : null}
    {create.error ? <p role="alert" className="text-sm text-danger">{financeError(create.error)}</p> : null}
  </div>;
}
