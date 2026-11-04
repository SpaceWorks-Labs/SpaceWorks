import { useState } from "react";
import { Card, ErrorText, StatusBadge } from "../../../components/ui";
import { StagePlanner } from "./StagePlanner";
import { useStaffCommand, useStaffQuery, type Stage } from "./api";

/** Stable criterion keys (`^[a-z][a-z0-9_]*$`) from the labels staff type, unique within the stage. */
export function criteriaFrom(labels: string[]) {
  const used = new Set<string>();
  return labels.map((label, index) => {
    let key = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 32) || "criterion";
    if (!/^[a-z]/.test(key)) key = "c_" + key;
    if (used.has(key)) key = `${key}_${index}`;
    used.add(key);
    return { key, label };
  });
}

/**
 * Multi-stage application review (#128 C-33): each stage has its own reviewer panel, criteria
 * (at most ten, scored 1 to 5), blind switch and 1 to 20 reviews per application. Criteria,
 * blind review and the target freeze at a stage's first review; the server enforces all of it.
 */
export function ReviewStagesPanel({ eventId }: { eventId: number }) {
  const stages = useStaffQuery<Stage[]>(eventId, "/application-stages/");
  const command = useStaffCommand<Stage>(eventId);
  const [name, setName] = useState(""), [target, setTarget] = useState(2), [blind, setBlind] = useState(false);
  const [criteria, setCriteria] = useState("Motivation\nExperience"), [open, setOpen] = useState<number | null>(null);
  const labels = criteria.split("\n").map(line => line.trim()).filter(Boolean);
  const create = () => command.mutate({ suffix: "/application-stages/", idempotent: true, body: {
    expected_version: 0, name, reviews_per_application: target, blind,
    criteria: criteriaFrom(labels),
  } }, { onSuccess: () => setName("") });
  const move = (stage: Stage, state: Stage["state"]) => command.mutate({ suffix: `/application-stages/${stage.id}/`,
    method: "PATCH", idempotent: true, body: { expected_version: stage.version, state } });
  if (stages.error) return <ErrorText message={stages.error.message} />;
  return <section className="grid gap-4" aria-labelledby="review-stages-heading">
    <header className="grid gap-1">
      <h3 id="review-stages-heading" className="text-lg font-semibold text-ink">Review stages</h3>
      <p className="text-sm text-muted">Applications move through the stages in order. Advance them from the decisions list.</p>
    </header>
    {command.error ? <ErrorText message={command.error.message} /> : null}
    {stages.isLoading ? <p role="status">Loading stages…</p> : null}
    {stages.data?.length === 0 ? <p className="text-sm text-muted">No stages yet. Without stages, applications use one review round.</p> : null}
    {stages.data?.map(stage => <Card key={stage.id}><div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-0.5">
          <p className="font-semibold text-ink">{stage.position}. {stage.name}</p>
          <p className="text-sm text-muted">{stage.reviews_per_application} review{stage.reviews_per_application === 1 ? "" : "s"} each
            · {stage.criteria.length} criteria{stage.blind ? " · blind" : ""} · {stage.standing} waiting · panel of {stage.panel.length}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {stage.frozen ? <StatusBadge status="locked" label="Criteria fixed" /> : null}
          <StatusBadge status={stage.state} label={stage.state} />
          {stage.state !== "open" ? <button type="button" className="desk-button" disabled={command.isPending}
            onClick={() => move(stage, "open")}>Open for review</button> : null}
          {stage.state === "open" ? <button type="button" className="desk-button" disabled={command.isPending}
            onClick={() => move(stage, "closed")}>Close</button> : null}
          <button type="button" className="desk-button" aria-expanded={open === stage.id}
            onClick={() => setOpen(open === stage.id ? null : stage.id)}>{open === stage.id ? "Hide panel and assignment" : "Panel and assignment"}</button>
        </div>
      </div>
      {open === stage.id ? <StagePlanner eventId={eventId} stage={stage} /> : null}
    </div></Card>)}
    <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault(); create(); }}>
      <p className="font-semibold text-ink">Add a stage</p>
      <label className="grid gap-1 text-sm text-ink">Name
        <input className="desk-input" required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
      <label className="grid gap-1 text-sm text-ink">Reviews per application (1 to 20)
        <input className="desk-input" type="number" min={1} max={20} value={target} onChange={e => setTarget(Number(e.target.value))} /></label>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="checkbox" checked={blind} onChange={e => setBlind(e.target.checked)} />Blind review (hide names and identifying answers)</label>
      <label className="grid gap-1 text-sm text-ink">Criteria, one per line (at most ten, each scored 1 to 5)
        <textarea className="desk-input min-h-24" value={criteria} onChange={e => setCriteria(e.target.value)} /></label>
      {labels.length > 10 ? <p role="alert" className="text-sm text-danger">Use at most ten criteria.</p> : null}
      <button type="submit" className="desk-button justify-self-start" disabled={command.isPending || !name.trim() || labels.length > 10
        || target < 1 || target > 20}>Add stage</button>
    </form></Card>
  </section>;
}
