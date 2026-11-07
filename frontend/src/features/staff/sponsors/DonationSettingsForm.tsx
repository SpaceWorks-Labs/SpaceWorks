import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Field } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { financeError } from "../../finance/financeApi";
import { donationStaffApi, donationStaffKeys, type DonationSettings } from "./staffDonationsApi";

function settingsError(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 403 && error.code === "setting_not_delegated") {
    return t`Only the Space Manager changes donation and tax-exempt settings.`;
  }
  return financeError(error);
}

/** The donation page's text and amounts, and the optional 80G registration (Space Manager only). */
export function DonationSettingsForm({ makerspaceId, taxOn }: { makerspaceId: number; taxOn: boolean }) {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: donationStaffKeys.settings(makerspaceId), queryFn: () => donationStaffApi.settings(makerspaceId) });
  const [form, setForm] = useState<DonationSettings | null>(null);
  const [amounts, setAmounts] = useState("");
  useEffect(() => {
    if (settings.data) { setForm(settings.data); setAmounts(settings.data.suggested_amounts.join(", ")); }
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () => donationStaffApi.saveSettings(makerspaceId, { ...form!,
      suggested_amounts: amounts.split(",").map(value => value.trim()).filter(Boolean) }),
    onSuccess: data => client.setQueryData(donationStaffKeys.settings(makerspaceId), data),
  });
  if (!form) return settings.error ? <p role="alert" className="text-sm text-danger">{financeError(settings.error)}</p>
    : <p role="status" className="text-sm text-muted">{t`Loading settings…`}</p>;
  const set = (patch: Partial<DonationSettings>) => setForm({ ...form, ...patch });
  return <Card><form className="grid gap-4" aria-label={t`Donation settings`} onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <Field label={t`Page introduction`}><textarea className="desk-input" rows={3} maxLength={500} value={form.page_intro}
      onChange={event => set({ page_intro: event.target.value })} /></Field>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t`Suggested amounts`} hint={t`Up to 8, separated by commas.`}><input className="desk-input tabular-nums"
        value={amounts} onChange={event => setAmounts(event.target.value)} /></Field>
      <Field label={t`Smallest gift`}><input className="desk-input tabular-nums" inputMode="decimal" required value={form.minimum_amount}
        onChange={event => set({ minimum_amount: event.target.value })} /></Field>
    </div>
    {taxOn ? <fieldset className="grid gap-3">
      <legend className="title-section">{t`80G registration`}</legend>
      <p className="text-sm text-muted">{t`Givers can ask for a tax-exempt receipt only while this registration is valid.`}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Registration number`}><input className="desk-input" maxLength={64} value={form.tax_exempt_registration_number}
          onChange={event => set({ tax_exempt_registration_number: event.target.value })} /></Field>
        <Field label={t`Institution's PAN`}><input className="desk-input uppercase" maxLength={10} value={form.tax_exempt_registrant_pan}
          onChange={event => set({ tax_exempt_registrant_pan: event.target.value })} /></Field>
        <Field label={t`Valid from`}><input className="desk-input" type="date" value={form.tax_exempt_valid_from ?? ""}
          onChange={event => set({ tax_exempt_valid_from: event.target.value || null })} /></Field>
        <Field label={t`Valid until`}><input className="desk-input" type="date" value={form.tax_exempt_valid_until ?? ""}
          onChange={event => set({ tax_exempt_valid_until: event.target.value || null })} /></Field>
      </div>
      <Field label={t`Note printed on the receipt`}><input className="desk-input" maxLength={300} value={form.tax_exempt_note}
        onChange={event => set({ tax_exempt_note: event.target.value })} /></Field>
    </fieldset> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{settingsError(save.error)}</p> : null}
    {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Saved.`}</p> : null}
    <button type="submit" className="desk-button justify-self-start" disabled={save.isPending}>{t`Save settings`}</button>
  </form></Card>;
}
