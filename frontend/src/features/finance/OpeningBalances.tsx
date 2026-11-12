import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { formatLocale } from "../../lib/format";
import { formatMoney } from "../staff/paymentsApi";
import { financeError, type FinanceAccess } from "./financeApi";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

export type OpeningBalance = { fy_start: string; currency: string; cash_amount: string; bank_amount: string; set_at: string };

const path = (id: number) => `/admin/makerspace/${id}/finance/opening-balances`;
const key = (id: number, fy: string) => ["finance", id, "opening-balances", fy] as const;
const MONEY = /^\d{1,10}(\.\d{1,3})?$/;

/**
 * Cash and bank balances a financial year starts from. Only finance staff for every area
 * see them; setting one appends a revision (the newest wins) and is audited by the server.
 */
export function OpeningBalances({ makerspaceId, access }: { makerspaceId: number; access: FinanceAccess }) {
  const client = useQueryClient();
  const [fy, setFy] = useState("");
  const [form, setForm] = useState({ currency: "", cash_amount: "", bank_amount: "" });
  const rows = useQuery({ queryKey: key(makerspaceId, fy),
    queryFn: () => staffRequest<OpeningBalance[]>(`${path(makerspaceId)}${fy ? `?fy=${fy}` : ""}`) });
  const save = useMutation({
    mutationFn: () => staffRequest<OpeningBalance>(path(makerspaceId), { method: "PUT", body: JSON.stringify({
      fy_start: fy || new Date().toISOString().slice(0, 10), currency: form.currency.trim().toLowerCase(),
      cash_amount: form.cash_amount.trim() || "0", bank_amount: form.bank_amount.trim() || "0" }) }),
    onSuccess: () => { setForm({ currency: "", cash_amount: "", bank_amount: "" }); void client.invalidateQueries({ queryKey: ["finance", makerspaceId] }); },
  });
  const ready = /^[a-zA-Z]{3}$/.test(form.currency.trim())
    && [form.cash_amount, form.bank_amount].every(value => !value.trim() || MONEY.test(value.trim()));
  return <div className="grid min-w-0 gap-4">
    <p className="text-sm text-muted">{t`What the year started with, in cash and in the bank. Totals elsewhere count from these. A change adds a new revision; the old one stays on record.`}</p>
    <Field label={t`Financial year containing`} hint={t`Any date inside the year. Leave blank for the current year.`}>
      <input className="desk-input" type="date" value={fy} onChange={event => setFy(event.target.value)} /></Field>
    {rows.isLoading ? <LogoLoader label={t`Loading opening balances…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.error ? <p role="alert" className="text-sm text-danger">{financeError(rows.error)}</p> : null}
    {rows.data && !rows.data.length ? <p className="text-sm text-muted">{t`No opening balances are set for this year.`}</p> : null}
    <ul className="grid gap-2">
      {(rows.data ?? []).map(row => <li key={row.currency} className="grid gap-1 rounded-lg border border-line bg-panel p-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="grid gap-1"><p className="font-semibold uppercase">{row.currency}</p>
          <p className="text-sm text-muted">{t`Year from ${row.fy_start} · set ${new Date(row.set_at).toLocaleDateString(formatLocale())}`}</p></div>
        <p className="tabular-nums">{t`Cash ${formatMoney(row.cash_amount, row.currency)} · Bank ${formatMoney(row.bank_amount, row.currency)}`}</p>
      </li>)}
    </ul>
    {access.record_everything ? <form className="grid gap-3 rounded-lg border border-line p-3" onSubmit={event => { event.preventDefault(); if (ready) save.mutate(); }}>
      <h3 className="title-section">{t`Set an opening balance`}</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t`Currency`}><input className="desk-input uppercase" required maxLength={3} placeholder={t`e.g. INR`} value={form.currency}
          onChange={event => setForm({ ...form, currency: event.target.value })} /></Field>
        <Field label={t`Cash`}><input className="desk-input" inputMode="decimal" placeholder="0.00" value={form.cash_amount}
          onChange={event => setForm({ ...form, cash_amount: event.target.value })} /></Field>
        <Field label={t`Bank`}><input className="desk-input" inputMode="decimal" placeholder="0.00" value={form.bank_amount}
          onChange={event => setForm({ ...form, bank_amount: event.target.value })} /></Field>
      </div>
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
      <div className="flex justify-end"><button type="submit" className="desk-button-primary" disabled={!ready || save.isPending}>
        {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save opening balance`}</button></div>
    </form> : null}
  </div>;
}
