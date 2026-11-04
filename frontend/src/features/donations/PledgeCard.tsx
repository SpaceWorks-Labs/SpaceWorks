import { useState } from "react";

import { Card, StatusPill } from "../../components/ui";
import { INTERVAL_LABELS, giveError, money, type Interval, type PledgeAction, type PledgeStatus } from "./donationsApi";

const TONES = { active: "success", paused: "warn", cancelled: "neutral" } as const;

/** One pledge with its own controls: pause, resume, change the amount or period, cancel. */
export function PledgeCard({ pledge, onAction, pending, error }: {
  pledge: PledgeStatus; onAction: (action: PledgeAction) => void; pending: boolean; error: unknown;
}) {
  const [amount, setAmount] = useState(pledge.amount);
  const [interval, setPeriod] = useState<Interval>(pledge.interval);
  const live = pledge.status !== "cancelled";
  return <Card><div className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-lg font-semibold tabular-nums text-ink">{money(pledge.currency, pledge.amount)} · {INTERVAL_LABELS[pledge.interval].toLowerCase()}</p>
      <StatusPill label={pledge.status[0].toUpperCase() + pledge.status.slice(1)} tone={TONES[pledge.status]} />
    </div>
    <p className="text-sm text-muted">To {pledge.makerspace}{pledge.campaign ? ` · ${pledge.campaign}` : ""}.
      {pledge.status === "active" ? ` Next reminder to pay on ${new Date(pledge.next_due_on).toLocaleDateString()}.` : ""}</p>
    {live ? <form className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" aria-label="Change this pledge"
      onSubmit={event => { event.preventDefault(); onAction({ action: "update", amount, interval }); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">Amount<input className="desk-input tabular-nums"
        inputMode="decimal" required pattern="[0-9]+(\.[0-9]{1,2})?" value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">How often<select className="desk-input" value={interval}
        onChange={event => setPeriod(event.target.value as Interval)}>
        {(Object.keys(INTERVAL_LABELS) as Interval[]).map(value => <option key={value} value={value}>{INTERVAL_LABELS[value]}</option>)}
      </select></label>
      <button type="submit" className="desk-button" disabled={pending}>Save changes</button>
    </form> : null}
    {live ? <div className="flex flex-wrap gap-2">
      {pledge.status === "active" ? <button type="button" className="desk-button" disabled={pending}
        onClick={() => onAction({ action: "pause" })}>Pause</button>
        : <button type="button" className="desk-button" disabled={pending} onClick={() => onAction({ action: "resume" })}>Resume</button>}
      <button type="button" className="desk-button-danger" disabled={pending} onClick={() => {
        if (window.confirm("Cancel this pledge? Gifts you already made stay recorded.")) onAction({ action: "cancel" });
      }}>Cancel pledge</button>
    </div> : <p className="text-sm text-muted">This pledge is cancelled. Thank you for your support.</p>}
    {error ? <p role="alert" className="text-sm text-danger">{giveError(error)}</p> : null}
  </div></Card>;
}
