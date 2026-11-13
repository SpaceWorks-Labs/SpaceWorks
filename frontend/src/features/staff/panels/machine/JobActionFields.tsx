import { t } from "@lingui/core/macro";
import { useId, type ReactNode } from "react";

import type { PrinterPool } from "../../../../generated/api";
import type { Machine } from "../../machinesApi";
import type { DialogAction, JobFormValues } from "./jobActionBody";
import { CHANGE_CODES, FAIL_CODES, REJECT_CODES } from "./jobLabels";
import { poolLabel } from "./servicePools";

type Props = {
  action: DialogAction; values: JobFormValues; set: (patch: Partial<JobFormValues>) => void;
  machines: Machine[]; pools: PrinterPool[]; unitLabel: string; hasPool: boolean; showOverride: boolean;
};

/** The form body of one board action. Labels are real `<label>`s so every control has an accessible name. */
export function JobActionFields({ action, values, set, machines, pools, unitLabel, hasPool, showOverride }: Props) {
  const id = useId();
  const text = (key: keyof JobFormValues, label: string, options: { numeric?: boolean; wide?: boolean; hint?: string; autoFocus?: boolean } = {}) =>
    <div className={`grid content-start gap-1 ${options.wide ? "sm:col-span-2" : ""}`}><label className="eyebrow grid gap-1">{label}
      <input className="desk-input" inputMode={options.numeric ? "decimal" : undefined} autoFocus={options.autoFocus}
        aria-describedby={options.hint ? `${id}-${key}-hint` : undefined}
        value={String(values[key])} onChange={event => set({ [key]: event.target.value })} /></label>
      {options.hint ? <p id={`${id}-${key}-hint`} className="text-xs text-muted">{options.hint}</p> : null}
    </div>;
  const select = (key: keyof JobFormValues, label: string, choices: [string, string][], empty: string) =>
    <label className="eyebrow grid gap-1">{label}<select className="desk-input" value={String(values[key])} onChange={event => set({ [key]: event.target.value })}>
      <option value="">{empty}</option>{choices.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
    </select></label>;
  const machineChoices = machines.map(machine => [String(machine.id), machine.name] as [string, string]);
  const poolSelect = hasPool ? <label className="eyebrow grid gap-1">{t`Consumable pool`}<select className="desk-input" value={values.consumable_pool_id}
    onChange={event => set({ consumable_pool_id: event.target.value })}><option value="">{t`No pool`}</option>
    {pools.map(pool => <option key={pool.id} value={pool.id}>{poolLabel(pool)}</option>)}</select></label> : null;
  const quantity = (label: string) => hasPool ? text("quantity", `${label} (${unitLabel})`, { numeric: true }) : null;
  const longText = (key: "message" | "note", label: string) => <label className="eyebrow grid gap-1 sm:col-span-2">{label}
    <textarea className="desk-input min-h-24" value={values[key]} onChange={event => set({ [key]: event.target.value })} /></label>;

  const bodies: Record<DialogAction, ReactNode> = {
    accept: <>{text("estimated_minutes", "Estimated minutes", { numeric: true, autoFocus: true })}{quantity("Planned")}
      {showOverride ? <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={values.override_length}
        onChange={event => set({ override_length: event.target.checked })} />{t`Accept anyway, longer than this type allows`}</label> : null}</>,
    start: <>{select("machine_id", "Machine", machineChoices, "Choose a machine")}{poolSelect}
      {text("estimated_minutes", "Estimated minutes", { numeric: true })}{quantity("Planned")}</>,
    quote: <>{text("estimated_minutes", "Estimated minutes", { numeric: true, autoFocus: true })}{quantity("Material")}{poolSelect}
      {longText("note", "Note to the member (optional)")}
      <p className="text-sm text-muted sm:col-span-2">{t`The price comes from the space’s rate card. The member has 7 days to approve it.`}</p></>,
    "request-changes": <>{select("code", "Reason", CHANGE_CODES, "Choose a reason")}{longText("message", "Message to the member")}</>,
    reject: <>{select("code", "Reason", REJECT_CODES, "Choose a reason (optional)")}{text("reason", "Explanation for the member", { wide: true })}</>,
    complete: <>{text("actual_minutes", "Actual minutes", { numeric: true })}{quantity("Actual")}
      {text("pickup_location", "Pickup place", { wide: true, hint: t`Where the member collects it, for example “Shelf B”.` })}</>,
    fail: <>{select("code", "What went wrong", FAIL_CODES, "Choose a reason (optional)")}
      <fieldset className="grid gap-2 sm:col-span-2"><legend className="eyebrow">{t`Whose fault`}</legend>
        {([["space", "The space or machine"], ["member", "The member or their file"]] as const).map(([value, label]) =>
          <label key={value} className="flex min-h-11 items-center gap-2 text-sm"><input type="radio" name={`${id}-fault`} value={value}
            checked={values.fault === value} onChange={() => set({ fault: value })} />{label}</label>)}
        <p className="text-sm text-muted">{t`A space fault puts the job back at the front of the queue for free. A member fault applies this type’s failure charge.`}</p>
      </fieldset>
      {text("percent_complete", "Percent complete", { numeric: true })}{text("actual_minutes", "Minutes run", { numeric: true })}
      {quantity("Material used")}{text("reason", "What happened", { wide: true })}</>,
    collect: <>{text("pickup_code", "Pickup code", { autoFocus: true, hint: t`Type or scan the code the member shows. Leave blank when you hand it to the member in person.` })}
      {text("collector_name", "Collected by (optional)", { hint: t`Name of whoever picks it up for the member.` })}</>,
    urgent: <>{text("reason", "Why it is urgent", { wide: true, autoFocus: true, hint: t`Urgent jobs move ahead of the normal queue.` })}</>,
    assign: <>{select("machine_id", "Machine", machineChoices, "Any machine (not assigned)")}</>,
  };
  return <div className="grid gap-3 sm:grid-cols-2">{bodies[action]}</div>;
}
