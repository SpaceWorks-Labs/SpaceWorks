import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { PrinterPool } from "../../../../generated/api";
import { Modal } from "../../../../components/ui";
import type { Machine } from "../../machinesApi";
import { splitByEstimate } from "./boardOrder";
import { ACTION_ERROR_HELP } from "./jobLabels";
import { errorCode, useBatchComplete, useBatchStart, type StaffJob } from "./machineJobsApi";
import { poolLabel } from "./servicePools";

type Plan = { estimated_minutes: string; consumable_pool_id: string; quantity: string };
const errorText = (error: Error | null) => error ? ACTION_ERROR_HELP[errorCode(error) ?? ""] ?? error.message : "";
const percent = (part: number, whole: number) => whole > 0 ? Math.round((part / whole) * 100) : 0;

/** Start two or more queued jobs as one machine run (`machines.batch_start`); each job keeps its own adjustable estimate. */
export function BatchStartDialog({ jobs, makerspaceId, typeId, machines, pools, unitLabel, hasPool, printer, onClose }: {
  jobs: StaffJob[]; makerspaceId: number; typeId: number; machines: Machine[]; pools: (machineId: string) => PrinterPool[];
  unitLabel: string; hasPool: boolean; printer: boolean; onClose: (done: boolean) => void;
}) {
  const start = useBatchStart(makerspaceId, typeId);
  const [machineId, setMachineId] = useState("");
  const [note, setNote] = useState("");
  const [plans, setPlans] = useState<Record<number, Plan>>(() => Object.fromEntries(jobs.map(job => [job.id,
    { estimated_minutes: String(job.estimated_minutes || job.member_estimate_minutes || 60), consumable_pool_id: "", quantity: "" }])));
  const total = jobs.reduce((sum, job) => sum + Number(plans[job.id].estimated_minutes || 0), 0);
  const update = (id: number, patch: Partial<Plan>) => setPlans(current => ({ ...current, [id]: { ...current[id], ...patch } }));
  const submit = () => start.mutate({
    job_ids: jobs.map(job => job.id), machine_id: Number(machineId), note: note.trim(),
    plans: Object.fromEntries(jobs.map(job => { const plan = plans[job.id]; return [String(job.id), {
      estimated_minutes: Number(plan.estimated_minutes || 0),
      ...(hasPool && plan.consumable_pool_id ? { consumable_pool_id: Number(plan.consumable_pool_id) } : {}),
      ...(hasPool && plan.quantity ? { [printer ? "planned_grams" : "planned_quantity"]: plan.quantity } : {}),
    }]; })),
  }, { onSuccess: () => onClose(true) });
  return <Modal open size="xl" title={t`Start ${jobs.length} jobs as one batch`} onClose={() => onClose(false)}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (machineId) submit(); }}>
      <label className="eyebrow grid gap-1">{t`Machine`}<select className="desk-input" value={machineId} onChange={event => setMachineId(event.target.value)}>
        <option value="">{t`Choose a machine`}</option>{machines.map(machine => <option key={machine.id} value={machine.id}>{machine.name}</option>)}</select></label>
      <ul className="grid gap-3" aria-label={t`Jobs in this batch`}>{jobs.map(job => { const plan = plans[job.id]; return <li key={job.id} className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-3">
        <p className="title-section sm:col-span-3">{job.title} <span className="text-sm font-normal text-muted">{t`· ${percent(Number(plan.estimated_minutes || 0), total)}% of the run`}</span></p>
        <label className="eyebrow grid gap-1">{t`Estimated minutes`}<input className="desk-input" inputMode="numeric" value={plan.estimated_minutes} onChange={event => update(job.id, { estimated_minutes: event.target.value })} /></label>
        {hasPool ? <><label className="eyebrow grid gap-1">{t`Pool`}<select className="desk-input" value={plan.consumable_pool_id} onChange={event => update(job.id, { consumable_pool_id: event.target.value })}>
          <option value="">{t`No pool`}</option>{pools(machineId).map(pool => <option key={pool.id} value={pool.id}>{poolLabel(pool)}</option>)}</select></label>
          <label className="eyebrow grid gap-1">{t`Planned ${unitLabel}`}<input className="desk-input" inputMode="decimal" value={plan.quantity} onChange={event => update(job.id, { quantity: event.target.value })} /></label></> : null}
      </li>; })}</ul>
      <p className="text-sm text-muted">{t`Estimated run: ${total} min in all. Each job keeps its own estimate, material and charge.`}</p>
      <label className="eyebrow grid gap-1">{t`Note (optional)`}<input className="desk-input" maxLength={200} value={note} onChange={event => setNote(event.target.value)} /></label>
      {start.error ? <p role="alert" className="text-sm text-danger">{errorText(start.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={() => onClose(false)}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!machineId || start.isPending}>{start.isPending ? t`Starting…` : t`Start batch`}</button>
      </div>
    </form>
  </Modal>;
}

/** Finish a batch run: one total for time and material, split across the jobs by their estimate share unless adjusted. */
export function BatchCompleteDialog({ batchId, jobs, makerspaceId, typeId, unitLabel, hasPool, onClose }: {
  batchId: number; jobs: StaffJob[]; makerspaceId: number; typeId: number; unitLabel: string; hasPool: boolean; onClose: () => void;
}) {
  const complete = useBatchComplete(makerspaceId, typeId);
  const [minutes, setMinutes] = useState(String(jobs.reduce((sum, job) => sum + (job.estimated_minutes || 0), 0)));
  const [quantity, setQuantity] = useState("");
  const [pickup, setPickup] = useState("");
  const [adjust, setAdjust] = useState(false);
  const [manual, setManual] = useState<Record<number, { minutes: string; quantity: string }>>({});
  const minuteSplit = splitByEstimate(jobs, Number(minutes || 0));
  const quantitySplit = splitByEstimate(jobs, Number(quantity || 0));
  const value = (id: number, key: "minutes" | "quantity") => manual[id]?.[key] ?? String((key === "minutes" ? minuteSplit : quantitySplit)[id]);
  const submit = () => complete.mutate({ batchId, body: {
    actual_minutes: Number(minutes || 0), ...(hasPool && quantity ? { actual_quantity: quantity } : {}), pickup_location: pickup.trim(),
    ...(adjust ? { splits: { minutes: Object.fromEntries(jobs.map(job => [String(job.id), Number(value(job.id, "minutes"))])),
      ...(hasPool && quantity ? { quantity: Object.fromEntries(jobs.map(job => [String(job.id), value(job.id, "quantity")])) } : {}) } } : {}),
  } }, { onSuccess: onClose });
  return <Modal open size="xl" title={t`Complete batch ${batchId}`} onClose={onClose}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); submit(); }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="eyebrow grid gap-1">{t`Total minutes`}<input className="desk-input" inputMode="numeric" value={minutes} onChange={event => setMinutes(event.target.value)} /></label>
        {hasPool ? <label className="eyebrow grid gap-1">{t`Total ${unitLabel} used`}<input className="desk-input" inputMode="decimal" value={quantity} onChange={event => setQuantity(event.target.value)} /></label> : null}
        <label className="eyebrow grid gap-1">{t`Pickup place`}<input className="desk-input" value={pickup} onChange={event => setPickup(event.target.value)} /></label>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={adjust} onChange={event => setAdjust(event.target.checked)} />{t`Adjust the split by hand`}</label>
      <ul className="grid gap-2" aria-label={t`Split per job`}>{jobs.map(job => <li key={job.id} className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-3 sm:items-center">
        <span className="title-section">{job.title}</span>
        {adjust ? <label className="eyebrow grid gap-1">{t`Minutes`}<input className="desk-input" inputMode="decimal" value={value(job.id, "minutes")}
          onChange={event => setManual(current => ({ ...current, [job.id]: { minutes: event.target.value, quantity: value(job.id, "quantity") } }))} /></label>
          : <span className="text-sm">{t`${minuteSplit[job.id]} min`}</span>}
        {hasPool && quantity ? adjust ? <label className="eyebrow grid gap-1">{unitLabel}<input className="desk-input" inputMode="decimal" value={value(job.id, "quantity")}
          onChange={event => setManual(current => ({ ...current, [job.id]: { minutes: value(job.id, "minutes"), quantity: event.target.value } }))} /></label>
          : <span className="text-sm">{quantitySplit[job.id]} {unitLabel}</span> : null}
      </li>)}</ul>
      {complete.error ? <p role="alert" className="text-sm text-danger">{errorText(complete.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-success" disabled={complete.isPending}>{complete.isPending ? t`Completing…` : t`Complete batch`}</button>
      </div>
    </form>
  </Modal>;
}
