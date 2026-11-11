import { t } from "@lingui/core/macro";
import { useState } from "react";

import { EmptyState, Field, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { incidentErrorMessage, useIncidentAssignees, type IncidentAction, type useIncidentChange } from "./api";

type Change = ReturnType<typeof useIncidentChange>;

/** Follow-up actions: what must happen next, who does it, by when, and whether it is done.
 *  The assignee is chosen from the staff who could triage this incident (never typed as an id). */
export function IncidentFollowUps({ incidentId, actions, add, toggle }: {
  incidentId: number; actions: IncidentAction[]; add: Change["addAction"]; toggle: Change["toggleAction"];
}) {
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const [assignee, setAssignee] = useState(0);
  const people = useIncidentAssignees(incidentId);
  const error = add.error ?? toggle.error;
  return <section aria-labelledby="incident-follow-ups-title" className="grid gap-4">
    <h2 id="incident-follow-ups-title" className="title-panel">{t`Follow-up actions`}</h2>
    {actions.length ? <ul className="grid gap-2">
      {actions.map(action => {
        const done = Boolean(action.done_at);
        const overdue = !done && action.due_date && action.due_date < new Date().toISOString().slice(0, 10);
        return <li key={action.id} className="flex min-w-0 flex-wrap items-center gap-3 rounded-xl border border-line bg-panel p-3">
          <div className="min-w-0 flex-1 basis-48">
            <p className={`break-words text-sm ${done ? "text-muted line-through" : "text-ink"}`}>{action.description}</p>
            <p className="text-xs text-muted">{[action.assignee_name ? t`With ${action.assignee_name}` : "",
              action.due_date ? t`Due ${formatDate(`${action.due_date}T00:00:00`)}` : "",
              action.done_at ? t`Done ${formatDate(action.done_at)}` : ""].filter(Boolean).join(" · ")}</p>
          </div>
          {overdue ? <StatusPill tone="danger" label={t`Overdue`} /> : null}
          <button type="button" className="desk-button" disabled={toggle.isPending}
            aria-label={done ? t`Reopen: ${action.description}` : t`Mark done: ${action.description}`}
            onClick={() => toggle.mutate({ actionId: action.id, done: !done })}>{done ? t`Reopen` : t`Mark done`}</button>
        </li>;
      })}
    </ul> : <EmptyState message={t`No follow-up actions yet. Add what needs to happen so nothing is forgotten.`} />}
    <form className="grid gap-3 rounded-xl border border-line bg-panel p-4 sm:grid-cols-2 sm:items-end lg:grid-cols-[1fr_auto_auto_auto]" onSubmit={event => {
      event.preventDefault();
      if (!description.trim() || add.isPending) return;
      add.mutate({ description: description.trim(), ...(due ? { due_date: due } : {}), ...(assignee ? { assignee_id: assignee } : {}) },
        { onSuccess: () => { setDescription(""); setDue(""); setAssignee(0); } });
    }}>
      <Field label={t`New follow-up action`}>
        <input className="desk-input" maxLength={300} value={description} onChange={event => setDescription(event.target.value)} />
      </Field>
      <Field label={t`Assign to (optional)`} hint={people.isError ? t`Staff list unavailable; add the action unassigned.` : undefined}>
        <select className="desk-input" value={assignee} disabled={!people.data} onChange={event => setAssignee(Number(event.target.value))}>
          <option value={0}>{people.isPending ? t`Loading staff…` : t`Nobody yet`}</option>
          {people.data?.results.map(person => <option key={person.id} value={person.id}>{person.display_name}</option>)}
        </select>
      </Field>
      <Field label={t`Due (optional)`}>
        <input className="desk-input" type="date" value={due} onChange={event => setDue(event.target.value)} />
      </Field>
      <button type="submit" className="desk-button-primary" disabled={!description.trim() || add.isPending}>
        {add.isPending ? t`Adding…` : t`Add action`}</button>
    </form>
    {error ? <p role="alert" className="text-sm text-danger">{incidentErrorMessage(error)}</p> : null}
  </section>;
}
