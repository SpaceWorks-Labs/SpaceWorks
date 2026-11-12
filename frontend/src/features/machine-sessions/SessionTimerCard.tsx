import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { StatusPill } from "../../components/ui";
import { money } from "../payments/usePriceQuote";
import type { MemberSession } from "./api";
import { clock, rateLine, when } from "./sessionFormat";
import { BoxArt } from "../../components/BoxSpinner";

/** Seconds since `startedAt`, re-read once a second while mounted. */
function useElapsed(startedAt: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return Math.max(0, (now - new Date(startedAt).getTime()) / 1000);
}

/**
 * The live session: a running clock, the frozen rate and the server's running amount, and
 * Stop. The clock is plain text (no animation), hidden from screen readers; the label
 * carries the start time instead so assistive tech is not read a number every second.
 */
export function SessionTimerCard({ session, maxMinutes, onStop, stopping, error }: {
  session: MemberSession; maxMinutes?: number; onStop: () => void; stopping: boolean; error?: string;
}) {
  const elapsed = useElapsed(session.started_at);
  return <section className="desk-panel grid gap-4 p-5" aria-labelledby={`session-${session.id}-title`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 id={`session-${session.id}-title`} className="title-panel">{session.machine_name}</h2>
      <StatusPill tone="info" icon="Clock" label={t`Session running`} />
    </div>
    <p className="font-display text-4xl tabular-nums text-ink" aria-hidden="true">{clock(elapsed)}</p>
    <p className="text-sm text-muted">{t`Started ${when(session.started_at)}`}
      {maxMinutes ? t` · stops by itself after ${maxMinutes} min, at check-out or at closing time` : ""}.</p>
    {session.rate ? <dl className="grid gap-1 text-sm">
      <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">{t`Rate`}</dt><dd>{rateLine(session.rate)}</dd></div>
      {session.amount != null ? <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted">{t`So far`}</dt>
        <dd className="tabular-nums">{money(session.amount, session.rate.currency)}</dd></div> : null}
    </dl> : <p className="text-sm text-muted">{t`This machine is free to use.`}</p>}
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <button type="button" className="desk-button-brand min-h-12 justify-self-stretch sm:justify-self-start" disabled={stopping} onClick={onStop}>
      {stopping ? <><BoxArt size={16} mono />{t`Stopping…`}</> : t`Stop session`}</button>
  </section>;
}
