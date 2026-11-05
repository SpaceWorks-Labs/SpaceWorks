import { Field, StatusPill } from "../../../components/ui";
import { Countdown, deadlineText } from "../stageTime";
import { BLOCKED, checklist, stageAnswers, answerKey, type ParticipantStage } from "./stageRules";
import type { Project } from "./types";

const STATUS = { upcoming: "Upcoming", open: "Open", late: "Open (late work is flagged)", closed: "Closed" } as const;
const SHORTLIST = { pending: "Shortlist pending", shortlisted: "Shortlisted", not_shortlisted: "Not shortlisted" } as const;

/** #178 / S13: every stage with its window in the event's and the viewer's time, and the team's progress. */
export function StageTracker({ stages, activeId, timezone }: { stages: readonly ParticipantStage[]; activeId: number | null; timezone: string }) {
  return <section className="grid gap-3" aria-label="Submission stages"><h3 className="font-semibold text-ink">Submission stages</h3>
    <ol className="grid gap-3">{stages.map(stage => <li key={stage.id} aria-current={stage.id === activeId ? "step" : undefined}
      className={`grid gap-2 rounded-2xl border p-3 ${stage.id === activeId ? "border-accent" : "border-line"}`}>
      <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-ink">{`${stage.position}. ${stage.name}`}</span>
        <StatusPill label={STATUS[stage.status]} tone={stage.status === "closed" ? "neutral" : stage.status === "upcoming" ? "info" : "success"} />
        {stage.submitted ? <StatusPill label="Submitted" tone="success" /> : null}
        {stage.shortlist_status ? <StatusPill label={`${stage.shortlist_label || "Shortlist"}: ${SHORTLIST[stage.shortlist_status]}`}
          tone={stage.shortlist_status === "shortlisted" ? "success" : stage.shortlist_status === "pending" ? "info" : "neutral"} /> : null}</div>
      {stage.description ? <p className="text-sm text-muted">{stage.description}</p> : null}
      <p className="text-sm text-ink">{`Deadline: ${deadlineText(stage.effective_deadline, timezone)}${stage.extended ? " (extended for your team)" : ""}`}</p>
      {stage.id === activeId && stage.status !== "closed" ? <Countdown deadline={stage.effective_deadline} /> : null}
      {stage.blocked ? <p className="text-sm text-warn-ink">{BLOCKED[stage.blocked]}</p> : null}
      {stage.feedback?.length ? <div className="grid gap-1"><p className="text-sm font-semibold text-ink">Feedback from the judges</p>
        <ul className="grid gap-1">{stage.feedback.map((text, i) => <li key={i} className="whitespace-pre-wrap rounded-2xl bg-surface p-3 text-sm text-ink">{text}</li>)}</ul></div> : null}
    </li>)}</ol></section>;
}

export function StageChecklist({ stage, project }: { stage: ParticipantStage; project: Project }) {
  const items = checklist(stage, project);
  if (!items.length) return <p className="text-sm text-muted">{stage.rules.content_mode === "presentation" ? "Nothing to upload for this stage; a deck is optional." : ""}</p>;
  return <section className="grid gap-2" aria-label={`Requirements for ${stage.name}`}><h3 className="font-semibold text-ink">{`Before you submit ${stage.name}`}</h3>
    <ul className="grid gap-1">{items.map(item => <li key={item.label} className={`text-sm ${item.met ? "text-success-ink" : "text-ink"}`}>
      {`${item.met ? "Done" : "To do"}: ${item.label}`}</li>)}</ul>
    {stage.rules.accepted_families.length ? <p className="text-sm text-muted">{`Accepted file types: ${stage.rules.accepted_families.join(", ")}.`}</p> : null}
    {stage.rules.video_hosts.length ? <p className="text-sm text-muted">{`Video links must be on: ${stage.rules.video_hosts.join(", ")}.`}</p> : null}
  </section>;
}

/** The stage's custom questions, stored in form_answers["stage:<id>"]. Required ones are checked at submit. */
export function StageAnswerFields({ stage, project, onChange }: { stage: ParticipantStage; project: Project; onChange: (answers: Record<string, unknown>) => void }) {
  if (!stage.custom_fields.length) return null;
  const answers = stageAnswers(project, stage);
  const set = (key: string, value: string) => onChange({ ...project.form_answers, [answerKey(stage)]: { ...answers, [key]: value } });
  return <fieldset className="grid gap-3"><legend className="font-semibold text-ink">{`${stage.name} questions`}</legend>
    {stage.custom_fields.map(field => <Field key={field.key} label={`${field.label}${field.required ? " (required)" : ""}`} hint={field.help || undefined}>
      {field.type === "long_text" ? <textarea className="desk-input min-h-24" maxLength={5000} value={answers[field.key] ?? ""} onChange={e => set(field.key, e.target.value)} />
        : field.type === "choice" ? <select className="desk-input min-h-11" value={answers[field.key] ?? ""} onChange={e => set(field.key, e.target.value)}>
          <option value="">Choose…</option>{(field.choices ?? []).map(choice => <option key={choice} value={choice}>{choice}</option>)}</select>
        : <input className="desk-input min-h-11" type={field.type === "url" ? "url" : "text"} maxLength={field.type === "url" ? 2048 : 200}
          value={answers[field.key] ?? ""} onChange={e => set(field.key, e.target.value)} />}</Field>)}
  </fieldset>;
}
