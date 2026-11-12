import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, StatusPill } from "../../components/ui";
import { useEventTicketing, type EventPromo } from "./eventTicketingApi";
import { EventPanelPager } from "./EventPanelPager";
import { panelEmpty, panelField, panelInput, panelReveal, panelRow } from "./eventPanelStyles";
import { LogoLoader } from "../../components/LogoLoader";

export function EventPromosPanel({ visible = true,  eventId, disabled = false }: { visible?: boolean;  eventId: number; disabled?: boolean }) {
  const [page, setPage] = useState(1);
  const { rows, create, revoke } = useEventTicketing<EventPromo>(eventId, "promo-codes", page);
  const [mode, setMode] = useState("percent");
  const [amount, setAmount] = useState("5.00");
  const [customCode, setCustomCode] = useState("");
  const [percent, setPercent] = useState(20);
  const [limit, setLimit] = useState(1);
  const [expiry, setExpiry] = useState("");
  const [code, setCode] = useState("");
  const error = rows.error || create.error || revoke.error;
  if (!visible) return null;
  return <section className="grid gap-4" aria-label={t`Event promo codes`}>
    <h3 className="title-section">{t`Promo codes`}</h3>
    <Card><form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); create.mutate({ ...(mode === "percent" ? { percent_off: percent } : { amount_off: amount }), ...(customCode ? { code: customCode } : {}), max_uses: limit, expires_at: expiry ? new Date(expiry).toISOString() : null }, { onSuccess: (row) => setCode(row.code ?? "") }); }}>
      <label className={panelField}>{t`Discount type`}<select className={panelInput} value={mode} disabled={disabled} onChange={(e) => setMode(e.target.value)}><option value="percent">{t`Percentage`}</option><option value="amount">{t`Fixed amount`}</option></select></label>
      <label className={panelField}>{t`Code (optional)`}<input className={panelInput} minLength={8} maxLength={128} value={customCode} disabled={disabled} onChange={(e) => setCustomCode(e.target.value)} /></label>
      {mode === "percent" ? <label className={panelField}>{t`Percent discount`}<input className={panelInput} type="number" required min="1" max="100" value={percent} disabled={disabled} onChange={(e) => setPercent(Number(e.target.value))} /></label> : <label className={panelField}>{t`Amount discount`}<input className={panelInput} type="number" required min="0.01" step="0.01" value={amount} disabled={disabled} onChange={(e) => setAmount(e.target.value)} /></label>}
      <label className={panelField}>{t`Maximum redemptions`}<input className={panelInput} type="number" required min="1" value={limit} disabled={disabled} onChange={(e) => setLimit(Number(e.target.value))} /></label>
      <label className={panelField}>{t`Promo expiry`}<input className={panelInput} type="datetime-local" value={expiry} disabled={disabled} onChange={(e) => setExpiry(e.target.value)} /></label>
      <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || create.isPending}>{t`Create promo code`}</button>
    </form></Card>
    {code ? <div role="status" className={panelReveal}><p>{t`Copy this code now. It is shown once.`}</p><output className="code-text break-all">{code}</output><button className="desk-button" type="button" onClick={() => setCode("")}>{t`Hide code`}</button></div> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
    {rows.isLoading ? <LogoLoader label={t`Loading promo codes…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.data?.results.length === 0 ? <p className={panelEmpty}>{t`No promo codes yet.`}</p> : null}
    {rows.data?.results.length ? <ul className="grid gap-3">{rows.data.results.map((row) => <li key={row.id} className={panelRow}>
      <div className="min-w-0"><p className="title-section">{t`Promo ${row.id}`}</p>
        <p className="mt-1 text-sm tabular-nums text-muted">{t`${row.percent_off ? `${row.percent_off}%` : row.amount_off} discount · ${row.uses}/${row.max_uses} uses`}</p></div>
      {row.revoked_at ? <StatusPill label={t`Revoked`} /> : <button className="desk-button-danger-outline" type="button" disabled={disabled || revoke.isPending} onClick={() => revoke.mutate(row.id)}>{t`Revoke promo ${row.id}`}</button>}
    </li>)}</ul> : null}
    <EventPanelPager page={page} setPage={setPage} count={rows.data?.count} previous={rows.data?.previous} next={rows.data?.next} />
  </section>;
}
