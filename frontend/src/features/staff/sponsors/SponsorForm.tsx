import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, Modal } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { sponsorApi, type Sponsor, type SponsorInput, type Tier } from "./staffSponsorsApi";

const blank: SponsorInput = { name: "", tier: null, website_url: "", blurb: "", contact_name: "", contact_email: "",
  contact_phone: "", starts_on: null, ends_on: null, show_on_wall: true };

/** Add or edit a sponsor. Name, logo, tier, website and blurb are public; the contact is private. */
export function SponsorForm({ makerspaceId, sponsor, tiers, onClose }: {
  makerspaceId: number; sponsor?: Sponsor; tiers: Tier[]; onClose: () => void;
}) {
  const client = useQueryClient();
  const [form, setForm] = useState<SponsorInput>(sponsor ? {
    name: sponsor.name, tier: sponsor.tier, website_url: sponsor.website_url, blurb: sponsor.blurb,
    contact_name: sponsor.contact_name, contact_email: sponsor.contact_email, contact_phone: sponsor.contact_phone,
    starts_on: sponsor.starts_on, ends_on: sponsor.ends_on, show_on_wall: sponsor.show_on_wall } : blank);
  const save = useMutation({
    mutationFn: () => sponsor ? sponsorApi.update(makerspaceId, sponsor.id, form) : sponsorApi.create(makerspaceId, form),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["staff-sponsors", makerspaceId] }); onClose(); },
  });
  const set = (patch: Partial<SponsorInput>) => setForm(current => ({ ...current, ...patch }));
  return <Modal open onClose={onClose} title={sponsor ? t`Edit ${sponsor.name}` : t`Add a sponsor`}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      <Field label={t`Name`}><input className="desk-input" required maxLength={150} value={form.name}
        onChange={event => set({ name: event.target.value })} /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Tier`}><select className="desk-input" value={form.tier ?? ""}
          onChange={event => set({ tier: event.target.value ? Number(event.target.value) : null })}>
          <option value="">{t`No tier`}</option>{tiers.map(tier => <option key={tier.id} value={tier.id}>{tier.name}</option>)}</select></Field>
        <Field label={t`Website`}><input className="desk-input" type="url" maxLength={300} value={form.website_url}
          onChange={event => set({ website_url: event.target.value })} /></Field>
        <Field label={t`From`}><input className="desk-input" type="date" value={form.starts_on ?? ""}
          onChange={event => set({ starts_on: event.target.value || null })} /></Field>
        <Field label={t`Until`}><input className="desk-input" type="date" value={form.ends_on ?? ""}
          onChange={event => set({ ends_on: event.target.value || null })} /></Field>
      </div>
      <Field label={t`One line for the sponsor wall`}><input className="desk-input" maxLength={300} value={form.blurb}
        onChange={event => set({ blurb: event.target.value })} /></Field>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.show_on_wall}
        onChange={event => set({ show_on_wall: event.target.checked })} />{t`Show on the public sponsor wall`}</label>
      <fieldset className="grid gap-3 sm:grid-cols-3"><legend className="text-sm font-semibold text-ink">{t`Private contact`}</legend>
        <Field label={t`Contact name`}><input className="desk-input" maxLength={200} value={form.contact_name}
          onChange={event => set({ contact_name: event.target.value })} /></Field>
        <Field label={t`Contact email`}><input className="desk-input" type="email" value={form.contact_email}
          onChange={event => set({ contact_email: event.target.value })} /></Field>
        <Field label={t`Contact phone`}><input className="desk-input" type="tel" maxLength={32} value={form.contact_phone}
          onChange={event => set({ contact_phone: event.target.value })} /></Field>
      </fieldset>
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
      <div className="flex justify-end gap-2"><button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button" disabled={save.isPending}>{sponsor ? t`Save` : t`Add sponsor`}</button></div>
    </form>
  </Modal>;
}
