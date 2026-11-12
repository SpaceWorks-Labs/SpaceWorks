import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, Modal } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { donationStaffApi, type DeskGiftInput, type StaffCampaign } from "./staffDonationsApi";
import { BoxArt } from "../../../components/BoxSpinner";

// `ManualSettlement.Method`: how the money reached the space.
const SETTLEMENT_METHODS = [["cash", "Cash"], ["upi", "UPI"], ["bank_transfer", "Bank transfer"], ["card_machine", "Card machine"],
  ["cheque", "Cheque"], ["other", "Other"]] as const;
const now = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

/** A gift handed over in person: the charge and its offline receipt in one go (maker-checker still applies). */
export function DeskGiftForm({ makerspaceId, campaigns, taxOn, onClose }: {
  makerspaceId: number; campaigns: StaffCampaign[]; taxOn: boolean; onClose: () => void;
}) {
  const client = useQueryClient();
  const [form, setForm] = useState<DeskGiftInput>({ amount: "", donor_name: "", donor_email: "", campaign: null, note: "",
    wants_tax_receipt: false, donor_pan: "", donor_address: "", settlement: { method: "cash", reference: "", received_at: now() } });
  const save = useMutation({
    mutationFn: () => donationStaffApi.recordDesk(makerspaceId, {
      ...form, settlement: { ...form.settlement, received_at: new Date(form.settlement.received_at).toISOString() } }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["staff-donations", makerspaceId] }); onClose(); },
  });
  const set = (patch: Partial<DeskGiftInput>) => setForm(current => ({ ...current, ...patch }));
  const settle = (patch: Partial<DeskGiftInput["settlement"]>) => set({ settlement: { ...form.settlement, ...patch } });
  return <Modal open onClose={onClose} title={t`Record a gift received in person`}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Amount`}><input className="desk-input tabular-nums" inputMode="decimal" required
          pattern="[0-9]+(\.[0-9]{1,2})?" value={form.amount} onChange={event => set({ amount: event.target.value })} /></Field>
        <Field label={t`Goes to`}><select className="desk-input" value={form.campaign ?? ""}
          onChange={event => set({ campaign: event.target.value ? Number(event.target.value) : null })}>
          <option value="">{t`General donation`}</option>
          {campaigns.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
        <Field label={t`Giver's name`}><input className="desk-input" required maxLength={200} value={form.donor_name}
          onChange={event => set({ donor_name: event.target.value })} /></Field>
        <Field label={t`Giver's email (optional)`}><input className="desk-input" type="email" value={form.donor_email}
          onChange={event => set({ donor_email: event.target.value })} /></Field>
        <Field label={t`Method`}><select className="desk-input" value={form.settlement.method}
          onChange={event => settle({ method: event.target.value })}>
          {SETTLEMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
        <Field label={t`Received`}><input className="desk-input" type="datetime-local" required value={form.settlement.received_at}
          onChange={event => settle({ received_at: event.target.value })} /></Field>
      </div>
      <Field label={t`Reference (optional)`}><input className="desk-input" maxLength={64} value={form.settlement.reference}
        onChange={event => settle({ reference: event.target.value })} /></Field>
      <Field label={t`Note (optional)`}><input className="desk-input" maxLength={500} value={form.note}
        onChange={event => set({ note: event.target.value })} /></Field>
      {taxOn ? <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.wants_tax_receipt}
        onChange={event => set({ wants_tax_receipt: event.target.checked })} />{t`Issue a tax receipt`}</label> : null}
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(form.recognize_publicly)}
        onChange={event => set({ recognize_publicly: event.target.checked })} />{t`The giver agreed to be named on the campaign page`}</label>
      {form.wants_tax_receipt ? <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Giver's PAN (India 80G only)`} hint={t`Stored encrypted.`}><input className="desk-input uppercase" maxLength={12}
          autoComplete="off" value={form.donor_pan} onChange={event => set({ donor_pan: event.target.value })} /></Field>
        <Field label={t`Giver's postal address`}><input className="desk-input" maxLength={500} value={form.donor_address}
          onChange={event => set({ donor_address: event.target.value })} /></Field>
      </div> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button" disabled={save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Record gift`}</button>
      </div>
    </form>
  </Modal>;
}
