import { t } from "@lingui/core/macro";
import { useEffect, useId, useState } from "react";

import { FILE_GROUPS } from "./jobLabels";
import { errorCode, useJobSettings, useSaveJobSettings, type JobSettings } from "./machineJobsApi";
import { useStaffChargesOn } from "../../useStaffChargesOn";

const READ_ONLY = (): Record<string, string> => ({
  setting_not_delegated: t`Only the Space Manager, or a manager they have handed these settings to, can change them.`,
  setting_locked: t`The Space Manager has locked these settings, so only they can change them.`,
});
const numberOrNull = (value: string) => value === "" ? null : Number(value);

/** Per-type job settings (#140/#142): intake, quotes, payment timing, failure charging, limits and accepted files. */
export function JobSettingsEditor({ makerspaceId, machineTypeId, visible = true }: { makerspaceId: number; machineTypeId: number; visible?: boolean }) {
  const id = useId();
  const query = useJobSettings(makerspaceId, machineTypeId, visible);
  const save = useSaveJobSettings(makerspaceId, machineTypeId);
  const [draft, setDraft] = useState<JobSettings | null>(null);
  const chargesOn = useStaffChargesOn("machines", makerspaceId); // #184: free machine jobs have no money settings
  useEffect(() => { if (query.data) setDraft(query.data); }, [query.data]);
  if (!visible) return null;
  const lockCode = [errorCode(save.error), errorCode(query.error)].find(code => code && READ_ONLY()[code]);
  const readOnly = !!lockCode;
  const set = (patch: Partial<JobSettings>) => setDraft(current => current ? { ...current, ...patch } : current);
  // The hint sits outside the label so the control's accessible name stays the short label.
  const field = (label: string, control: React.ReactNode, hint?: string) => <div className="grid content-start gap-1">
    <label className="grid gap-1 text-sm">{label}{control}</label>
    {hint ? <p className="text-xs text-muted">{hint}</p> : null}</div>;
  return <section className="rounded-xl border border-line bg-panel p-3" aria-labelledby={`${id}-title`}>
    <h3 id={`${id}-title`} className="title-panel">{t`Job requests`}</h3>
    <p className="my-2 text-sm text-muted">{t`How members send jobs to this machine type, how they are priced, and what a failed job costs.`}</p>
    {lockCode ? <p role="status" className="mb-2 rounded-md border border-line bg-surface p-3 text-sm">{READ_ONLY()[lockCode]}</p> : null}
    {query.isLoading ? <p role="status">{t`Loading job settings…`}</p> : null}
    {draft ? <form className="grid gap-3" onSubmit={event => { event.preventDefault();
      // A refused save shows the stored values read-only, never the edit the server would not take.
      save.mutate(draft, { onError: error => { if (READ_ONLY()[errorCode(error) ?? ""] && query.data) setDraft(query.data); } }); }}>
      <fieldset className="grid gap-3 sm:grid-cols-2" disabled={readOnly || save.isPending}>
        <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={draft.accepts_job_requests}
          onChange={event => set({ accepts_job_requests: event.target.checked })} />{t`Members can send job requests for this type`}</label>
        {!chargesOn ? <p className="text-sm text-muted sm:col-span-2">{t`Machine charges are off in this space, so jobs are free: no quote, no payment and no failure charge. The stored money settings come back when charges are turned on.`}</p> : null}
        {chargesOn ? <>{field("Quotes", <select className="desk-input" value={draft.quote_mode} onChange={event => set({ quote_mode: event.target.value as JobSettings["quote_mode"] })}>
          <option value="auto">{t`When the job has a price`}</option><option value="always">{t`Always`}</option><option value="above">{t`Above an amount`}</option><option value="off">{t`Never`}</option>
        </select>, "A quote is a price the member approves before the job joins the queue.")}
        {draft.quote_mode === "above" ? field("Quote above this amount", <input className="desk-input" inputMode="decimal" value={draft.quote_above_amount ?? ""}
          onChange={event => set({ quote_above_amount: event.target.value || null })} />) : null}
        {field("When members pay", <select className="desk-input" value={draft.payment_timing} onChange={event => set({ payment_timing: event.target.value as JobSettings["payment_timing"] })}>
          <option value="completion">{t`When the job is done`}</option><option value="prepay">{t`Before the job joins the queue`}</option></select>)}
        {field("If a job fails through the member’s fault", <select className="desk-input" value={draft.member_fault_charge}
          onChange={event => set({ member_fault_charge: event.target.value as JobSettings["member_fault_charge"] })}>
          <option value="none">{t`Charge nothing`}</option><option value="material_only">{t`Charge the material used`}</option><option value="full">{t`Charge the full job`}</option>
        </select>, "A failure the space or machine caused is always free and goes back to the front of the queue.")}</> : null}
        {field("Open jobs per member", <input className="desk-input" type="number" min={1} value={draft.max_open_jobs ?? ""}
          onChange={event => set({ max_open_jobs: numberOrNull(event.target.value) })} />, "Blank for no limit.")}
        {field("Longest job (minutes)", <input className="desk-input" type="number" min={1} value={draft.max_job_minutes ?? ""}
          onChange={event => set({ max_job_minutes: numberOrNull(event.target.value) })} />, "Longer jobs need a staff override. Blank for no limit.")}
        {field("Runs without staff present", <select className="desk-input" value={draft.runs_unattended === null ? "" : draft.runs_unattended ? "yes" : "no"}
          onChange={event => set({ runs_unattended: event.target.value === "" ? null : event.target.value === "yes" })}>
          <option value="">{t`Default for this type`}</option><option value="yes">{t`Yes`}</option><option value="no">{t`No`}</option></select>)}
        <fieldset className="grid gap-1 sm:col-span-2"><legend className="text-sm">{t`Accepted files`}</legend>
          <p className="text-xs text-muted">{t`None ticked uses this type’s usual formats.`}</p>
          <div className="grid gap-1 sm:grid-cols-2">{FILE_GROUPS.map(([value, label]) => <label key={value} className="flex min-h-11 items-center gap-2 text-sm">
            <input type="checkbox" checked={draft.file_groups.includes(value)} onChange={event => set({ file_groups: event.target.checked
              ? [...draft.file_groups, value] : draft.file_groups.filter(group => group !== value) })} />{label}</label>)}</div>
        </fieldset>
      </fieldset>
      {!readOnly ? <button className="desk-button-primary w-fit" disabled={save.isPending}>{save.isPending ? t`Saving…` : t`Save job settings`}</button> : null}
      {save.isSuccess ? <p role="status" className="text-sm">{t`Job settings saved.`}</p> : null}
    </form> : null}
    {[query.error, save.error].map((error, index) => error instanceof Error && !(errorCode(error) && READ_ONLY()[errorCode(error)!])
      ? <p className="text-sm text-danger" role="alert" key={index}>{error.message}</p> : null)}
  </section>;
}
