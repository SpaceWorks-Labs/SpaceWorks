import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { formatMoney } from "../../lib/money";
import { useState } from "react";

import { Card, StatusPill } from "../../components/ui";
import { INTERVAL_LABELS, giveError, type Interval, type PledgeAction, type PledgeStatus } from "./donationsApi";

const TONES = { active: "success", paused: "warn", cancelled: "neutral" } as const;

function pledgeStatusLabel(status: PledgeStatus["status"]) {
  return status === "active" ? t`Active` : status === "paused" ? t`Paused` : t`Cancelled`;
}

/** One pledge with its own controls: pause, resume, change the amount or period, cancel. */
export function PledgeCard({ pledge, onAction, pending, error }: {
  pledge: PledgeStatus; onAction: (action: PledgeAction) => void; pending: boolean; error: unknown;
}) {
  const [amount, setAmount] = useState(pledge.amount);
  const [interval, setPeriod] = useState<Interval>(pledge.interval);
  const live = pledge.status !== "cancelled";
  return <Card><div className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-lg font-semibold tabular-nums text-ink">{t`${formatMoney(pledge.amount, pledge.currency)} · ${INTERVAL_LABELS[pledge.interval]}`}</p>
      <StatusPill label={pledgeStatusLabel(pledge.status)} tone={TONES[pledge.status]} />
    </div>
    <p className="text-sm text-muted">{t`To ${pledge.makerspace}${pledge.campaign ? ` · ${pledge.campaign}` : ""}.`}{pledge.status === "active" ? t` Next reminder to pay on ${new Date(pledge.next_due_on).toLocaleDateString(formatLocale())}.` : ""}</p>
    {live ? <form className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" aria-label={t`Change this pledge`}
      onSubmit={event => { event.preventDefault(); onAction({ action: "update", amount, interval }); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Amount`}<input className="desk-input tabular-nums"
        inputMode="decimal" required pattern="[0-9]+(\.[0-9]{1,3})?" value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`How often`}<select className="desk-input" value={interval}
        onChange={event => setPeriod(event.target.value as Interval)}>
        {(Object.keys(INTERVAL_LABELS) as Interval[]).map(value => <option key={value} value={value}>{INTERVAL_LABELS[value]}</option>)}
      </select></label>
      <button type="submit" className="desk-button" disabled={pending}>{t`Save changes`}</button>
    </form> : null}
    {live ? <div className="flex flex-wrap gap-2">
      {pledge.status === "active" ? <button type="button" className="desk-button" disabled={pending}
        onClick={() => onAction({ action: "pause" })}>{t`Pause`}</button>
        : <button type="button" className="desk-button" disabled={pending} onClick={() => onAction({ action: "resume" })}>{t`Resume`}</button>}
      <button type="button" className="desk-button-danger" disabled={pending} onClick={() => {
        if (window.confirm(t`Cancel this pledge? Gifts you already made stay recorded.`)) onAction({ action: "cancel" });
      }}>{t`Cancel pledge`}</button>
    </div> : <p className="text-sm text-muted">{t`This pledge is cancelled. Thank you for your support.`}</p>}
    {error ? <p role="alert" className="text-sm text-danger">{giveError(error)}</p> : null}
  </div></Card>;
}
