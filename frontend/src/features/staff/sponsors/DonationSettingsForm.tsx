import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Field } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { financeError } from "../../finance/financeApi";
import { donationStaffApi, donationStaffKeys, type DonationSettings } from "./staffDonationsApi";
import { TaxExemptionsEditor } from "./TaxExemptionsEditor";
import { LogoLoader } from "../../../components/LogoLoader";

function settingsError(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 403 && error.code === "setting_not_delegated") {
    return t`Only the Space Manager changes donation settings and the non-profit profile.`;
  }
  return financeError(error);
}

/**
 * The donation page's text and amounts, and the non-profit profile (decision 242(m)): Space Manager only.
 * On, tax receipts can be issued under a valid registration and the public pages show a Donate link;
 * off, gifts still work and every receipt says it is not a tax receipt.
 */
export function DonationSettingsForm({ makerspaceId, taxOn, canEdit = true }: {
  makerspaceId: number; taxOn: boolean; canEdit?: boolean;
}) {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: donationStaffKeys.settings(makerspaceId), queryFn: () => donationStaffApi.settings(makerspaceId) });
  const [form, setForm] = useState<DonationSettings | null>(null);
  const [amounts, setAmounts] = useState("");
  useEffect(() => {
    if (settings.data) {
      setForm({ ...settings.data, tax_exemptions: settings.data.tax_exemptions ?? [] });
      setAmounts(settings.data.suggested_amounts.join(", "));
    }
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () => donationStaffApi.saveSettings(makerspaceId, { ...form!,
      suggested_amounts: amounts.split(",").map(value => value.trim()).filter(Boolean) }),
    onSuccess: data => client.setQueryData(donationStaffKeys.settings(makerspaceId), data),
  });
  if (!form) return settings.error ? <p role="alert" className="text-sm text-danger">{financeError(settings.error)}</p>
    : <LogoLoader label={t`Loading settings…`} size={48} className="min-h-16 py-3" />;
  const set = (patch: Partial<DonationSettings>) => setForm({ ...form, ...patch });
  const india = form.tax_exemptions.some(row => row.scheme === "in_80g");
  return <Card><form className="grid gap-4" aria-label={t`Donation settings`} onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    {!canEdit ? <p className="text-sm text-muted">{t`Only the Space Manager changes these settings.`}</p> : null}
    <fieldset disabled={!canEdit} className="grid min-w-0 gap-4">
      <Field label={t`Page introduction`}><textarea className="desk-input" rows={3} maxLength={500} value={form.page_intro}
        onChange={event => set({ page_intro: event.target.value })} /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Suggested amounts`} hint={t`Up to 8, separated by commas.`}><input className="desk-input tabular-nums"
          value={amounts} onChange={event => setAmounts(event.target.value)} /></Field>
        <Field label={t`Smallest gift`}><input className="desk-input tabular-nums" inputMode="decimal" required value={form.minimum_amount}
          onChange={event => set({ minimum_amount: event.target.value })} /></Field>
      </div>
      <fieldset className="grid gap-3">
        <legend className="title-section">{t`Non-profit profile`}</legend>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.is_nonprofit}
          onChange={event => set({ is_nonprofit: event.target.checked })} />{t`This makerspace is a non-profit`}</label>
        <p className="text-sm text-muted">{form.is_nonprofit
          ? t`Your public pages show a Donate link, and givers can ask for a tax receipt while a registration below is valid.`
          : t`Gifts still work, but no tax receipts are issued and every receipt says it is not a tax receipt.`}</p>
        {form.is_nonprofit ? <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t`Legal name`} hint={t`Printed at the top of every receipt.`}><input className="desk-input" maxLength={200}
              value={form.legal_name} onChange={event => set({ legal_name: event.target.value })} /></Field>
            <Field label={t`Registration number`} hint={t`Your trust, society, charity or company number.`}><input className="desk-input"
              maxLength={64} value={form.organization_registration_number}
              onChange={event => set({ organization_registration_number: event.target.value })} /></Field>
          </div>
          {taxOn ? <TaxExemptionsEditor rows={form.tax_exemptions} onChange={rows => set({ tax_exemptions: rows })} />
            : <p className="text-sm text-muted">{t`Turn on "Tax-exempt donation receipts" under Features to add tax-exemption registrations.`}</p>}
          {taxOn && india ? <Field label={t`Institution's PAN`} hint={t`Printed on 80G receipts.`}><input className="desk-input uppercase"
            maxLength={10} value={form.tax_exempt_registrant_pan}
            onChange={event => set({ tax_exempt_registrant_pan: event.target.value })} /></Field> : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t`Receipt signed by`}><input className="desk-input" maxLength={120} value={form.signatory_name}
              onChange={event => set({ signatory_name: event.target.value })} /></Field>
            <Field label={t`Their title`}><input className="desk-input" maxLength={120} value={form.signatory_title}
              onChange={event => set({ signatory_title: event.target.value })} /></Field>
          </div>
          <Field label={t`Receipt footer`} hint={t`A line printed at the bottom of every tax receipt.`}><textarea className="desk-input"
            rows={2} maxLength={500} value={form.receipt_footer} onChange={event => set({ receipt_footer: event.target.value })} /></Field>
        </> : null}
      </fieldset>
      {save.error ? <p role="alert" className="text-sm text-danger">{settingsError(save.error)}</p> : null}
      {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Saved.`}</p> : null}
      {canEdit ? <button type="submit" className="desk-button justify-self-start" disabled={save.isPending}>{t`Save settings`}</button> : null}
    </fieldset>
  </form></Card>;
}
