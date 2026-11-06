import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Receipt } from "lucide-react";

import { Field, SettingsRow } from "../../components/ui";
import { downloadStaffFile, staffRequest } from "../../lib/api";
import { formatMoney } from "../staff/paymentsApi";
import { financeError } from "./financeApi";

type Tax = {
  enabled: boolean; mode: "none" | "single" | "gst_india"; tax_name: string; rate_bps: number; prices_include_tax: boolean;
  gstin: string; state_code: string; scheme: "regular" | "composition"; exempt: boolean; sac_code: string;
  foreign_currency: "no_gst" | "export_lut"; lut_number: string; invoice_prefix: string; credit_note_prefix: string;
};
type Preview = { title: string; currency: string; taxable: string; tax: string; gross: string; supply_type: string;
  components: { code: string; label: string; rate_bps: number; amount: string }[]; notes: string[]; sample_number: string };
type Editable = Omit<Tax, "enabled">;

const MODES = [["none", "No tax"], ["single", "One named tax (VAT, sales tax)"], ["gst_india", "India GST"]] as const;

/** Tax policy (`billing.tax`): mode picker, live sample invoice and the GSTR-1 download. Space Manager only. */
export function TaxSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const path = `/admin/makerspace/${makerspaceId}/billing/tax`;
  const policy = useQuery({ queryKey: ["billing-tax", makerspaceId], queryFn: () => staffRequest<Tax>(path) });
  const [draft, setDraft] = useState<Editable | null>(null);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  useEffect(() => { if (policy.data) { const { enabled: _enabled, ...rest } = policy.data; setDraft(rest); } }, [policy.data]);
  const preview = useQuery({
    queryKey: ["billing-tax-preview", makerspaceId, JSON.stringify(draft)], enabled: Boolean(draft && policy.data?.enabled),
    queryFn: () => staffRequest<Preview>(`${path}/preview`, { method: "POST", body: JSON.stringify({ amount: "1000.00",
      currency: "inr", settings: draft }) }), retry: false,
  });
  const save = useMutation({
    mutationFn: () => staffRequest<Tax>(path, { method: "PUT", body: JSON.stringify(draft) }),
    onSuccess: data => client.setQueryData(["billing-tax", makerspaceId], data),
  });
  if (!policy.data || !draft) return null;
  if (!policy.data.enabled) {
    return <SettingsRow label={t`Tax`} helper="Turn on “Tax on charges” under Features to charge VAT or India GST. Until then no tax is charged and documents stay exactly as they are." >{null}</SettingsRow>;
  }
  const set = (patch: Partial<Editable>) => setDraft({ ...draft, ...patch });
  const gst = draft.mode === "gst_india";
  return <SettingsRow label={t`Tax`} helper="Applies to charges raised from now on. Existing charges and issued documents never change.">
    <form className="grid min-w-0 gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      <fieldset className="grid gap-2"><legend className="text-sm font-semibold">{t`How you charge tax`}</legend>
        {MODES.map(([value, label]) => <label key={value} className="flex min-h-11 items-center gap-2">
          <input type="radio" name="tax-mode" checked={draft.mode === value} onChange={() => set({ mode: value })} />{label}</label>)}
      </fieldset>
      {draft.mode !== "none" ? <div className="grid gap-3 sm:grid-cols-2">
        {draft.mode === "single" ? <Field label={t`Tax name`}><input className="desk-input" maxLength={32} value={draft.tax_name} onChange={event => set({ tax_name: event.target.value })} /></Field> : null}
        <Field label={t`Rate (%)`}><input className="desk-input" inputMode="decimal" value={draft.rate_bps / 100}
          onChange={event => set({ rate_bps: Math.round(Number(event.target.value || 0) * 100) })} /></Field>
        <label className="flex min-h-11 items-center gap-2 sm:col-span-2"><input type="checkbox" checked={draft.prices_include_tax}
          onChange={event => set({ prices_include_tax: event.target.checked })} />{t`Prices already include tax`}</label>
      </div> : null}
      {gst ? <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`GSTIN`}><input className="desk-input font-mono uppercase" maxLength={15} value={draft.gstin} onChange={event => set({ gstin: event.target.value.toUpperCase(), state_code: event.target.value.slice(0, 2) })} /></Field>
        <Field label={t`SAC code`}><input className="desk-input" maxLength={8} value={draft.sac_code} onChange={event => set({ sac_code: event.target.value })} /></Field>
        <Field label={t`Scheme`}><select className="desk-input" value={draft.scheme} onChange={event => set({ scheme: event.target.value as Editable["scheme"] })}>
          <option value="regular">{t`Regular`}</option><option value="composition">{t`Composition`}</option></select></Field>
        <Field label={t`Charges in other currencies`}><select className="desk-input" value={draft.foreign_currency}
          onChange={event => set({ foreign_currency: event.target.value as Editable["foreign_currency"] })}>
          <option value="no_gst">{t`Outside GST`}</option><option value="export_lut">{t`Export under LUT`}</option></select></Field>
        {draft.foreign_currency === "export_lut" ? <Field label={t`LUT number`}><input className="desk-input" maxLength={32} value={draft.lut_number} onChange={event => set({ lut_number: event.target.value })} /></Field> : null}
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={draft.exempt} onChange={event => set({ exempt: event.target.checked })} />{t`Our services are exempt`}</label>
      </div> : null}
      {draft.mode !== "none" ? <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Invoice prefix (max 4)`}><input className="desk-input uppercase" maxLength={4} value={draft.invoice_prefix} onChange={event => set({ invoice_prefix: event.target.value.toUpperCase() })} /></Field>
        <Field label={t`Credit-note prefix (max 4)`}><input className="desk-input uppercase" maxLength={4} value={draft.credit_note_prefix} onChange={event => set({ credit_note_prefix: event.target.value.toUpperCase() })} /></Field>
      </div> : null}
      {preview.data ? <aside aria-live="polite" className="grid gap-1 rounded-xl border border-line bg-panel p-4 text-sm">
        <p className="flex items-center gap-2 font-semibold"><Receipt aria-hidden="true" size={16} />{t`Sample: ${preview.data.title} ${preview.data.sample_number}`}</p>
        <p>{t`Taxable value ${formatMoney(preview.data.taxable, preview.data.currency)}`}</p>
        {preview.data.components.map(item => <p key={item.code}>{item.label} @ {item.rate_bps / 100}%: {formatMoney(item.amount, preview.data!.currency)}</p>)}
        <p className="font-semibold">{t`Total ${formatMoney(preview.data.gross, preview.data.currency)}`}</p>
        {preview.data.notes.map(note => <p key={note} className="text-muted">{note}</p>)}
      </aside> : null}
      {preview.error ? <p role="alert" className="text-sm text-danger">{financeError(preview.error)}</p> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
      {save.isSuccess ? <p role="status" className="text-sm">{t`Tax settings saved.`}</p> : null}
      <button type="submit" className="desk-button justify-self-start" disabled={save.isPending}>{t`Save tax settings`}</button>
    </form>
    {gst ? <div className="mt-4 flex flex-wrap items-end gap-2">
      <Field label={t`GSTR-1 month`}><input type="month" className="desk-input" value={month} onChange={event => setMonth(event.target.value)} /></Field>
      <button type="button" className="desk-button-ghost" onClick={() => void downloadStaffFile(`${path}/gstr1.json?month=${month}`, `GSTR1-${month}.json`)}>
        {t`Download GSTR-1 JSON`}</button>
    </div> : null}
  </SettingsRow>;
}
