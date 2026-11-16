import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorText } from "../../../components/ui";
import { useEventStaffGrants } from "../eventStaffGrantsApi";
import { useStaffCommand, useStaffQuery, type Plan, type ProgressRow, type Stage } from "./api";

/**
 * One stage's reviewer panel, its seeded assignment and its progress. The preview writes
 * nothing; "Apply" sends the preview's seed and fingerprint, and the server refuses when the
 * applications or the panel changed since, so staff always apply exactly what they saw.
 */
export function StagePlanner({ eventId, stage }: { eventId: number; stage: Stage }) {
  const grants = useEventStaffGrants({ kind: "event", id: eventId }, 1, true);
  const command = useStaffCommand<Stage>(eventId);
  const planner = useStaffCommand<Plan>(eventId);
  const progress = useStaffQuery<ProgressRow[]>(eventId, `/application-stages/${stage.id}/progress/`);
  const [chosen, setChosen] = useState<number[]>(stage.panel.map(row => row.reviewer_id));
  const [manual, setManual] = useState(""), [seed, setSeed] = useState(stage.assignment_seed);
  const [strategy, setStrategy] = useState(stage.assignment_strategy), [plan, setPlan] = useState<Plan | null>(null);
  const [advancing, setAdvancing] = useState<number[]>([]);
  const decisions = useStaffCommand<{ id: number; version: number }>(eventId);
  const advance = () => decisions.mutate({ suffix: "/application-decisions/stage/", idempotent: true, body: {
    expected_version: 0, decisions: (progress.data ?? []).filter(row => advancing.includes(row.application_id)).map(row => ({
      application_id: row.application_id, expected_version: row.version, outcome: "advance", reason_code: "stage_review",
      stage_id: stage.id })) } }, { onSuccess: batch => decisions.mutate({ suffix: "/application-decisions/release/",
    idempotent: true, body: { expected_version: batch.version, batch_id: batch.id } }, { onSuccess: () => setAdvancing([]) }) });
  const people = new Map<number, string>(stage.panel.map(row => [row.reviewer_id, row.label]));
  (grants.data?.results ?? []).forEach(row => { if (!people.has(row.user)) people.set(row.user, `Event team member #${row.user}`); });
  chosen.forEach(id => { if (!people.has(id)) people.set(id, `Account #${id}`); });
  const toggle = (id: number, on: boolean) => setChosen(on ? [...chosen, id] : chosen.filter(value => value !== id));
  const savePanel = () => command.mutate({ suffix: `/application-stages/${stage.id}/panel/`, method: "PUT", idempotent: true,
    body: { expected_version: stage.version, reviewer_ids: chosen } });
  const preview = () => planner.mutate({ suffix: `/application-stages/${stage.id}/assignment-preview/`,
    body: { strategy, ...(seed ? { seed } : {}) } }, { onSuccess: result => { setPlan(result); setSeed(result.seed); } });
  const apply = () => plan && command.mutate({ suffix: `/application-stages/${stage.id}/assignment-apply/`, idempotent: true,
    body: { expected_version: 0, seed: plan.seed, strategy: plan.strategy, fingerprint: plan.fingerprint } },
  { onSuccess: () => setPlan(null) });
  return <div className="grid gap-4 border-t border-line pt-3">
    {command.error || planner.error || decisions.error
      ? <ErrorText message={(command.error ?? planner.error ?? decisions.error)!.message} /> : null}
    <fieldset className="grid gap-2">
      <legend className="text-sm font-semibold text-ink">{t`Reviewer panel`}</legend>
      <p className="text-sm text-muted">{t`Panel members see only this stage's review workspace and their own assignments.`}</p>
      {[...people].map(([id, label]) => <label key={id} className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="checkbox" checked={chosen.includes(id)} onChange={e => toggle(id, e.target.checked)} />{label}</label>)}
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-sm text-ink">{t`Add by account number`}<input className="desk-input" inputMode="numeric" value={manual} onChange={e => setManual(e.target.value.replace(/\D/g, ""))} /></label>
        <button type="button" className="desk-button" disabled={!manual} onClick={() => {
          const id = Number(manual); if (id && !chosen.includes(id)) setChosen([...chosen, id]); setManual(""); }}>{t`Add`}</button>
        <button type="button" className="desk-button" disabled={command.isPending} onClick={savePanel}>{t`Save panel`}</button>
      </div>
    </fieldset>
    <div className="grid gap-2">
      <p className="text-sm font-semibold text-ink">{t`Assign reviewers`}</p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-sm text-ink">{t`Strategy`}<select className="desk-input" value={strategy} onChange={e => setStrategy(e.target.value as Stage["assignment_strategy"])}>
            <option value="balanced">{t`Balanced workload`}</option><option value="random">{t`Random`}</option></select></label>
        <label className="grid gap-1 text-sm text-ink">{t`Seed (kept, so the plan can be reproduced)`}<input className="desk-input" value={seed} maxLength={64} onChange={e => setSeed(e.target.value.replace(/[^A-Za-z0-9_-]/g, ""))} /></label>
        <button type="button" className="desk-button" disabled={planner.isPending} onClick={preview}>{t`Preview`}</button>
      </div>
      {plan ? <div className="grid gap-2" role="status">
        <p className="text-sm text-ink">{t`${plan.pairs.length} new assignments for ${plan.applications} applications`}{plan.deficits.length ? t`; ${plan.deficits.length} still short of reviewers` : ""}.</p>
        <button type="button" className="desk-button justify-self-start" disabled={command.isPending || !plan.pairs.length}
          onClick={apply}>{t`Apply this plan`}</button>
      </div> : null}
    </div>
    <div className="grid gap-1">
      <p className="text-sm font-semibold text-ink">{t`Progress`}</p>
      {progress.data?.length === 0 ? <p className="text-sm text-muted">{t`No applications are waiting in this stage.`}</p> : null}
      <ul className="grid gap-1">{progress.data?.map(row => <li key={row.application_id} className="flex flex-wrap justify-between gap-2 text-sm text-ink">
        <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={advancing.includes(row.application_id)}
          onChange={e => setAdvancing(e.target.checked ? [...advancing, row.application_id]
            : advancing.filter(id => id !== row.application_id))} />{row.alias}</label>
        <span className="text-muted">{row.reviews} of {row.needed} reviews
          {row.average !== null ? t` · average ${row.average}` : ""}</span></li>)}</ul>
      <button type="button" className="desk-button justify-self-start" disabled={!advancing.length || decisions.isPending}
        onClick={advance}>{t`Advance selected to the next stage`}</button>
    </div>
  </div>;
}
