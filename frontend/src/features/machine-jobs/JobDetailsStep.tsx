import { t } from "@lingui/core/macro";
import { Field } from "../../components/ui";
import { IntakeFields, type IntakeValues, type TypeIntake } from "../inventory/MachineIntakeForm";
import { groupPoolsByMaterial } from "../printing/PublicPrintRequestForm";
import type { PublicFilamentPool } from "../printing/publicApi";
import { todayIso, type JobDraft } from "./jobDraft";
import type { JobType } from "./types";

type Props = {
  draft: JobDraft; update: (patch: Partial<JobDraft>) => void; type: JobType;
  intake?: TypeIntake; pools?: PublicFilamentPool[]; poolsError?: Error | null; disabled?: boolean;
};

/** The printer's material pickers: the space's catalogue (material, then colour) and its live spools. */
function PrinterMaterial({ draft, update, intake, pools, poolsError }: Omit<Props, "type">) {
  const colours = intake?.materials.find(row => row.name === draft.material)?.colours ?? [];
  return <div className="grid gap-4 md:grid-cols-2">
    {intake?.materials.length ? <>
      <Field label={t`Material`}><select className="desk-input w-full" value={draft.material}
        onChange={event => update({ material: event.target.value, color: "", poolId: "" })}>
        <option value="">{t`No preference`}</option>{intake.materials.map(row => <option key={row.name}>{row.name}</option>)}</select></Field>
      <Field label={t`Colour`}><select className="desk-input w-full" value={draft.color} disabled={!draft.material}
        onChange={event => update({ color: event.target.value })}>
        <option value="">{t`Choose a colour`}</option>{colours.map(colour => <option key={colour}>{colour}</option>)}</select></Field>
    </> : null}
    {pools?.length ? <Field label={t`Filament in stock`} hint={t`Pick a spool, or leave it to staff.`}>
      <select className="desk-input w-full" value={draft.poolId} onChange={event => {
        const pool = pools.find(row => String(row.id) === event.target.value);
        update({ poolId: event.target.value, ...(pool ? { material: pool.material, color: pool.color } : {}) });
      }}>
        <option value="">{t`No preference`}</option>
        {groupPoolsByMaterial(pools).map(([material, rows]) => <optgroup key={material} label={material}>
          {rows.map(pool => <option key={pool.id} value={pool.id}>{pool.color || t`Default colour`}</option>)}</optgroup>)}
      </select></Field> : null}
    {poolsError ? <p className="text-sm text-danger" role="alert">{t`Couldn't load the filament list. You can still send the job; staff will confirm the material.`}</p> : null}
    <Field label={t`Estimated filament in grams (optional)`} hint={t`From your slicer, if you know it. Staff can adjust it.`}>
      <input className="desk-input w-full tabular-nums" type="number" min={0} step="0.01" value={draft.grams} onChange={event => update({ grams: event.target.value })} />
    </Field>
  </div>;
}

/** Step 3: what to make, how many, by when, and on what material. */
export function JobDetailsStep({ draft, update, type, intake, pools, poolsError, disabled }: Props) {
  return <fieldset className="grid gap-5" disabled={disabled}>
    <legend className="title-section mb-1">{t`Job details`}</legend>
    <Field label={t`Title`}><input className="desk-input w-full" required maxLength={200} value={draft.title} onChange={event => update({ title: event.target.value })} /></Field>
    <Field label={t`Notes for staff (optional)`} hint={t`Size, finish, anything staff should know.`}>
      <textarea className="desk-input min-h-24 w-full" maxLength={4000} value={draft.description} onChange={event => update({ description: event.target.value })} />
    </Field>
    <div className="grid gap-4 md:grid-cols-2">
      <Field label={t`Copies`}><input className="desk-input w-full tabular-nums" type="number" min={1} max={999} value={draft.copies}
        onChange={event => update({ copies: Math.trunc(Number(event.target.value)) || 1 })} /></Field>
      <Field label={t`Needed by (optional)`} hint={t`Staff try to plan around it; it isn't a promise.`}>
        <input className="desk-input w-full" type="date" min={todayIso()} value={draft.neededBy} onChange={event => update({ neededBy: event.target.value })} />
      </Field>
    </div>
    <Field label={t`Source link (optional)`} hint={t`Where the design came from, for example a model page.`}>
      <input className="desk-input w-full" type="url" inputMode="url" value={draft.sourceLink} onChange={event => update({ sourceLink: event.target.value })} />
    </Field>
    {type.is_printer ? <Field label={t`Slicer settings or preferences (optional)`}>
      <textarea className="desk-input min-h-20 w-full" value={draft.settings} onChange={event => update({ settings: event.target.value })} />
    </Field> : intake?.intake_schema.fields?.length ? <div className="grid gap-3">
      <IntakeFields intake={intake} values={draft.intake} setValues={change => update({ intake: change(draft.intake) as IntakeValues })} />
    </div> : null}
    <label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-ink">
      <input type="checkbox" className="h-5 w-5 shrink-0 accent-brand" checked={draft.ownMaterial} onChange={event => update({ ownMaterial: event.target.checked })} />
      {t`I'm bringing my own material`}</label>
    {draft.ownMaterial ? <Field label={t`Your material`} hint={t`What it is and how much, so staff can check it suits the machine.`}>
      <input className="desk-input w-full" maxLength={200} value={draft.materialNote} onChange={event => update({ materialNote: event.target.value })} />
    </Field> : type.is_printer ? <PrinterMaterial draft={draft} update={update} intake={intake} pools={pools} poolsError={poolsError} /> : null}
  </fieldset>;
}
