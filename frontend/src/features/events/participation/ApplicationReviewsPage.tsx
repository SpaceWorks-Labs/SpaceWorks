import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { Card, ErrorText, StatusBadge } from "../../../components/ui";

type Criterion = { key: string; label: string; guidance?: string };
type ReviewStage = { id: number; event_id: number; event_title?: string; name: string; position: number; blind: boolean;
  criteria: Criterion[]; guidance: string; assigned?: number; submitted?: number };
type Answer = { id: string; label: string; value: unknown };
type Assignment = { id: number; state: string; application: { id: number; alias: string; answers: Answer[] };
  scores: Record<string, number> | null; allowed_actions: string[] };

/**
 * The review-panel workspace: the stages whose panel I sit on, and only my own assignments.
 * Sitting on a panel gives no other access to the event. Web only until the native event-role
 * contract exists (#173).
 */
export function ApplicationReviewsPage() {
  const stages = useQuery({ queryKey: ["my-review-stages"], retry: false,
    queryFn: () => memberRequest<ReviewStage[]>("/admin/my-application-reviews/") });
  const [current, setCurrent] = useState<ReviewStage | null>(null);
  return <main className="mx-auto grid max-w-3xl gap-4 p-4">
    <h1 className="font-display text-2xl text-ink">Application reviews</h1>
    {stages.error ? <ErrorText message={stages.error.message} /> : null}
    {stages.data?.length === 0 ? <p className="text-muted">You have no open review stages.</p> : null}
    {current ? <StageWorkspace stage={current} onBack={() => setCurrent(null)} /> : <ul className="grid gap-2">
      {stages.data?.map(stage => <li key={stage.id}><Card><div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="font-semibold text-ink">{stage.event_title} · {stage.name}</p>
          <p className="text-sm text-muted">{stage.assigned ?? 0} to review, {stage.submitted ?? 0} done{stage.blind ? " · blind" : ""}</p></div>
        <button type="button" className="desk-button" onClick={() => setCurrent(stage)}>Open</button>
      </div></Card></li>)}</ul>}
  </main>;
}

function StageWorkspace({ stage, onBack }: { stage: ReviewStage; onBack: () => void }) {
  const base = `/admin/events/${stage.event_id}/application-stages/${stage.id}/my-reviews/`;
  const client = useQueryClient(), key = ["my-stage-reviews", stage.id];
  const work = useQuery({ queryKey: key, retry: false,
    queryFn: () => memberRequest<{ assignments: Assignment[] }>(base) });
  const [scores, setScores] = useState<Record<number, Record<string, number>>>({}), [notes, setNotes] = useState<Record<number, string>>({});
  const submit = useMutation({ mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
    memberRequest<Assignment>(`${base}${id}/`, { method: "POST", body: JSON.stringify(body) }),
  onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  const set = (id: number, criterion: string, value: number) => setScores({ ...scores, [id]: { ...scores[id], [criterion]: value } });
  return <div className="grid gap-3">
    <button type="button" className="desk-button justify-self-start" onClick={onBack}>All my stages</button>
    <h2 className="text-lg font-semibold text-ink">{stage.name}</h2>
    {stage.guidance ? <p className="text-sm text-muted">{stage.guidance}</p> : null}
    {stage.blind ? <p className="text-sm text-muted">Blind review: names and identifying answers are hidden. Do not try to identify applicants.</p> : null}
    {work.error || submit.error ? <ErrorText message={(work.error ?? submit.error)!.message} /> : null}
    {work.data?.assignments.map(row => <Card key={row.id}><div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold text-ink">{row.application.alias}</p>
        <StatusBadge status={row.state} label={row.state} /></div>
      <dl className="grid gap-2">{row.application.answers.map(answer => <div key={answer.id}>
        <dt className="text-sm font-semibold text-ink">{answer.label}</dt>
        <dd className="text-sm text-ink">{typeof answer.value === "string" ? answer.value : JSON.stringify(answer.value)}</dd></div>)}</dl>
      {row.allowed_actions.includes("submit") ? <form className="grid gap-2" onSubmit={event => { event.preventDefault();
        submit.mutate({ id: row.id, body: { scores: scores[row.id] ?? {}, notes: notes[row.id] ?? "" } }); }}>
        {stage.criteria.map(criterion => <fieldset key={criterion.key} className="flex flex-wrap items-center gap-2">
          <legend className="text-sm text-ink">{criterion.label}</legend>
          {[1, 2, 3, 4, 5].map(value => <label key={value} className="flex min-h-11 min-w-11 items-center justify-center gap-1 text-sm text-ink">
            <input type="radio" name={`${row.id}-${criterion.key}`} checked={scores[row.id]?.[criterion.key] === value}
              onChange={() => set(row.id, criterion.key, value)} />{value}</label>)}
        </fieldset>)}
        <label className="grid gap-1 text-sm text-ink">Private notes<textarea className="desk-input min-h-16" maxLength={5000}
          value={notes[row.id] ?? ""} onChange={e => setNotes({ ...notes, [row.id]: e.target.value })} /></label>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="desk-button" disabled={submit.isPending
            || Object.keys(scores[row.id] ?? {}).length !== stage.criteria.length}>Submit review</button>
          <button type="button" className="desk-button" disabled={submit.isPending}
            onClick={() => submit.mutate({ id: row.id, body: { recusal_code: "declared" } })}>I have a conflict</button>
        </div>
      </form> : null}
    </div></Card>)}
  </div>;
}
