import { LogoLoader } from "../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";

import { ConfirmDialog, StatusPill } from "../../components/ui";
import { formatDateTime, formatTime } from "../../lib/format";
import { supervisedErrorMessage, useSupervisedSession, useSupervisedSteps, type SupervisedSession } from "./api";
import { SuperviseeAdd } from "./SuperviseeAdd";

/** One supervised session: who is supervised, each person's use of the machine, and closing it.
 *  `picker` replaces the people search (the staff console passes its member picker). */
export function SupervisedSessionManager({ sessionId, picker }: {
  sessionId: number; picker?: (value: string, onChange: (value: string) => void) => ReactNode;
}) {
  const query = useSupervisedSession(sessionId);
  const steps = useSupervisedSteps(sessionId);
  const [closing, setClosing] = useState(false);
  const session = query.data;
  if (query.isLoading) return <LogoLoader label={t`Loading the session…`} />;
  if (query.error || !session) return <div role="alert" className="grid justify-items-start gap-2 text-sm text-danger">
    <p>{supervisedErrorMessage(query.error)}</p>
    <button type="button" className="desk-button" onClick={() => void query.refetch()}>{t`Try again`}</button></div>;
  const error = [steps.add, steps.remove, steps.start, steps.end, steps.close].find(step => step.error)?.error;
  const busy = [steps.add, steps.remove, steps.start, steps.end, steps.close].some(step => step.isPending);
  const active = session.participants.filter(row => !row.removed_at);
  const earlier = session.participants.filter(row => row.removed_at);
  return <section aria-labelledby={`supervised-${session.id}-title`} className="grid min-w-0 gap-4 rounded-xl border border-line bg-panel p-4">
    <header className="flex min-w-0 flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <h3 id={`supervised-${session.id}-title`} className="title-panel break-words">{t`Supervised session on ${session.machine_name}`}</h3>
        <p className="text-sm text-muted">{[t`Led by ${session.instructor_name}`, t`Opened ${formatDateTime(session.opened_at)}`,
          session.event ? t`Event #${session.event}` : "", session.closed_at ? t`Closed ${formatDateTime(session.closed_at)}` : ""].filter(Boolean).join(" · ")}</p>
        {session.note ? <p className="mt-1 break-words text-sm">{session.note}</p> : null}
      </div>
      <StatusPill tone={session.is_open ? "success" : "neutral"} label={session.is_open ? t`Open` : t`Closed`} />
    </header>
    <div className="grid gap-2">
      <h4 className="title-section">{t`Supervisees`}</h4>
      {active.length ? <ul className="grid gap-2">{active.map(row => <Supervisee key={row.user} session={session} userId={row.user} name={row.name}
        busy={busy} steps={steps} />)}</ul>
        : <p className="text-sm text-muted">{session.is_open ? t`Nobody yet. Add each person you supervise before they use the machine.` : t`Nobody was supervised.`}</p>}
      {earlier.length ? <p className="text-xs text-muted">{t`Removed: ${earlier.map(row => row.name).join(", ")}`}</p> : null}
    </div>
    {session.is_open ? <SuperviseeAdd sessionId={session.id} pending={steps.add.isPending} picker={picker} onAdd={(userId, done) => steps.add.mutate(userId, { onSuccess: done })} /> : null}
    {error ? <p role="alert" className="text-sm text-danger">{supervisedErrorMessage(error)}</p> : null}
    <p className="text-xs text-muted">{t`${session.uses.length} uses recorded in this session.`}</p>
    {session.is_open ? <button type="button" className="desk-button-danger-outline justify-self-start" disabled={busy}
      onClick={() => setClosing(true)}>{t`Close session`}</button> : null}
    <ConfirmDialog open={closing} title={t`Close this supervised session?`} tone="danger" confirmLabel={t`Close session`}
      message={t`Every use still in progress ends now, and supervisees can no longer use the machine under this session.`}
      pending={steps.close.isPending} onCancel={() => setClosing(false)}
      onConfirm={() => steps.close.mutate(undefined, { onSettled: () => setClosing(false) })} />
  </section>;
}

function Supervisee({ session, userId, name, busy, steps }: {
  session: SupervisedSession; userId: number; name: string; busy: boolean; steps: ReturnType<typeof useSupervisedSteps>;
}) {
  const live = session.uses.find(use => use.user === userId && !use.ended_at);
  const count = session.uses.filter(use => use.user === userId).length;
  return <li className="flex min-w-0 flex-wrap items-center gap-2 rounded-xl border border-line p-3">
    <div className="min-w-0 flex-1 basis-40">
      <p className="break-words text-sm font-semibold">{name} <span className="font-normal text-muted">#{userId}</span></p>
      <p className="text-xs text-muted">{live ? t`Using the machine since ${formatTime(live.started_at)}` : t`${count} uses so far`}</p>
    </div>
    {session.is_open ? <div className="flex flex-wrap gap-2">
      {live ? <button type="button" className="desk-button" disabled={busy} aria-label={t`End use for ${name}`}
        onClick={() => steps.end.mutate(live.id)}>{t`End use`}</button>
        : <button type="button" className="desk-button-primary" disabled={busy} aria-label={t`Start use for ${name}`}
          onClick={() => steps.start.mutate(userId)}>{t`Start use`}</button>}
      <button type="button" className="desk-button-ghost" disabled={busy} aria-label={t`Remove ${name}`}
        onClick={() => steps.remove.mutate(userId)}>{t`Remove`}</button>
    </div> : null}
  </li>;
}
