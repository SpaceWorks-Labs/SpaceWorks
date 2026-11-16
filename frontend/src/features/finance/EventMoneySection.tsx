import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { downloadStaffFile } from "../../lib/api";
import { formatMoney } from "../staff/paymentsApi";
import { financeApi, financeError, type FinanceAccess } from "./financeApi";

/** One event's money: income less refunds and what was spent on it, against its budget (X55). */
export function EventMoneySection({ makerspaceId, access }: { makerspaceId: number; access: FinanceAccess }) {
  const client = useQueryClient();
  const [eventId, setEventId] = useState("");
  const [budget, setBudget] = useState({ currency: "inr", amount: "" });
  const id = Number(eventId);
  const money = useQuery({ queryKey: ["finance-event", makerspaceId, id], queryFn: () => financeApi.eventMoney(makerspaceId, id),
    enabled: Number.isInteger(id) && id > 0 });
  const save = useMutation({
    mutationFn: () => financeApi.setBudget(makerspaceId, id, budget.currency, budget.amount),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["finance-event", makerspaceId, id] }); setBudget({ ...budget, amount: "" }); },
  });
  const canBudget = access.record_everything || access.record_domains.includes("events");
  return <div className="grid min-w-0 gap-4">
    <Field label={t`Event number`} hint={t`Shown on the event's page in the console.`}><input className="desk-input" inputMode="numeric"
      value={eventId} onChange={event => setEventId(event.target.value.replace(/\D/g, ""))} /></Field>
    {money.error ? <p role="alert" className="text-sm text-danger">{financeError(money.error)}</p> : null}
    {money.data && !money.data.length ? <p className="text-sm text-muted">{t`No money recorded for this event yet.`}</p> : null}
    {(money.data ?? []).map(row => <article key={row.currency} className="grid gap-1 rounded-xl border border-line bg-panel p-4 text-sm">
      <h3 className="title-section">{row.event || t`Event ${row.event_id}`} · {row.currency.toUpperCase()}</h3>
      <p>{t`Income ${formatMoney(row.income, row.currency)} · refunds ${formatMoney(row.refunds, row.currency)}`}</p>
      <p>{t`Spent ${formatMoney(String(Number(row.expenses) + Number(row.payouts)), row.currency)} (expenses and payouts)`}</p>
      <p>{t`Budget `}{row.budget === null ? t`not set` : formatMoney(row.budget, row.currency)}
        {row.budget_left === null ? "" : t` · ${formatMoney(row.budget_left, row.currency)} left`}</p>
      <p className="font-semibold">{t`Net ${formatMoney(row.net, row.currency)}`}</p>
    </article>)}
    {money.data ? <button type="button" className="desk-button-ghost justify-self-start"
      onClick={() => void downloadStaffFile(`/admin/makerspace/${makerspaceId}/finance/events/${id}?format=csv`, `event-${id}-money.csv`)}>
      {t`Download money CSV`}</button> : null}
    {money.data && canBudget ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      <Field label={t`Budget currency`}><input className="desk-input w-24" maxLength={3} value={budget.currency}
        onChange={event => setBudget({ ...budget, currency: event.target.value.toLowerCase() })} /></Field>
      <Field label={t`Budget amount`}><input className="desk-input" inputMode="decimal" required value={budget.amount}
        onChange={event => setBudget({ ...budget, amount: event.target.value })} /></Field>
      <button type="submit" className="desk-button" disabled={save.isPending}>{t`Set budget`}</button>
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
    </form> : null}
  </div>;
}
