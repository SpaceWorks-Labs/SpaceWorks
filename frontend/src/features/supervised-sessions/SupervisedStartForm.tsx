import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field } from "../../components/ui";
import { supervisedErrorMessage, useOpenSupervisedSession, type SupervisedSession } from "./api";
import { SupervisedMachineSelect } from "./SupervisedMachineSelect";

/** "Start a supervised session": a certified instructor opens one on a machine, optionally for
 *  an event. `machineId` is fixed on a machine's own page; elsewhere the machine is chosen from the
 *  member machine list (or typed by number when that list is not available to the person). */
export function SupervisedStartForm({ makerspaceId, machineId, onOpened }: {
  makerspaceId: number; machineId?: number; onOpened: (session: SupervisedSession) => void;
}) {
  const open = useOpenSupervisedSession();
  const [machine, setMachine] = useState("");
  const [note, setNote] = useState("");
  const [event, setEvent] = useState("");
  const target = machineId ?? (/^\d+$/.test(machine) ? Number(machine) : 0);
  const digits = (value: string) => value.replace(/\D/g, "");
  return <form className="grid gap-4 rounded-xl border border-line bg-panel p-4" aria-labelledby="supervised-start-title" onSubmit={submit => {
    submit.preventDefault();
    if (!target || open.isPending) return;
    open.mutate({ machineId: target, ...(note.trim() ? { note: note.trim() } : {}), ...(event ? { event_id: Number(event) } : {}) },
      { onSuccess: session => { setNote(""); setEvent(""); onOpened(session); } });
  }}>
    <div className="grid gap-1">
      <h3 id="supervised-start-title" className="title-panel">{t`Start a supervised session`}</h3>
      <p className="text-sm text-muted">{t`For instructors certified on the machine. People you add may use it while the session is open, and each use is recorded under you.`}</p>
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      {machineId ? null : <SupervisedMachineSelect makerspaceId={makerspaceId} value={machine} onChange={setMachine} />}
      <Field label={t`Event number (optional)`} hint={t`If this session is part of a workshop event.`}>
        <input className="desk-input" inputMode="numeric" pattern="[0-9]*" value={event} onChange={change => setEvent(digits(change.target.value))} />
      </Field>
    </div>
    <Field label={t`Note (optional)`}>
      <input className="desk-input" maxLength={300} value={note} onChange={change => setNote(change.target.value)} />
    </Field>
    {open.error ? <p role="alert" className="text-sm text-danger">{supervisedErrorMessage(open.error)}</p> : null}
    <button type="submit" className="desk-button-primary justify-self-start" disabled={!target || open.isPending}>
      {open.isPending ? t`Opening…` : t`Open session`}</button>
  </form>;
}
