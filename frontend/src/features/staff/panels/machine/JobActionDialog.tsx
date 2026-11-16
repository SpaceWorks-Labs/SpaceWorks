import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { PrinterPool } from "../../../../generated/api";
import { Modal } from "../../../../components/ui";
import { EntryFields } from "../../../machine-consumables/EntryFields";
import type { EntryValues } from "../../../machine-consumables/entries";
import { activeRows, consumableBlocker, consumableEntries, CONSUMABLE_ACTIONS } from "./jobConsumableGate";
import { useJobConsumables } from "./jobConsumablesApi";
import type { Machine } from "../../machinesApi";
import { JobActionFields } from "./JobActionFields";
import { initialJobValues, jobActionBody, jobFormBlocker, type DialogAction, type JobFormValues } from "./jobActionBody";
import { ACTION_ERROR_HELP } from "./jobLabels";
import { errorCode, useJobAction, type StaffJob } from "./machineJobsApi";
import { BoxArt } from "../../../../components/BoxSpinner";

const TITLES: Record<DialogAction, string> = {
  accept: t`Accept job`, start: t`Start job`, quote: t`Send quote`, "request-changes": t`Ask for changes`, reject: t`Reject job`,
  complete: t`Complete job`, fail: t`Mark job failed`, collect: t`Hand over job`, urgent: t`Mark urgent`, assign: t`Assign to a machine`,
};
const CONFIRM: Partial<Record<DialogAction, string>> = { quote: "Send quote", "request-changes": "Send to member", reject: "Reject job",
  fail: "Mark failed", collect: "Mark collected", urgent: "Pin as urgent", assign: "Save machine" };

type Props = {
  job: StaffJob; action: DialogAction; makerspaceId: number; typeId: number; machines: Machine[];
  pools: (machineId: string) => PrinterPool[]; unitLabel: string; hasPool: boolean; printer: boolean; onClose: () => void;
};

/** One modal for every board action. A priced type answering `quote_required` turns Accept into Send quote in place. */
export function JobActionDialog({ job, action: initialAction, makerspaceId, typeId, machines, pools, unitLabel, hasPool, printer, onClose }: Props) {
  const [action, setAction] = useState<DialogAction>(initialAction);
  const [values, setValues] = useState<JobFormValues>(() => initialJobValues(job));
  const [notice, setNotice] = useState("");
  const [entries, setEntries] = useState<EntryValues>({});
  const run = useJobAction(makerspaceId, typeId);
  const set = (patch: Partial<JobFormValues>) => setValues(current => ({ ...current, ...patch }));
  const code = errorCode(run.error);
  // Decision 341: the type's consumable profile. A refused or absent profile simply adds nothing to the form.
  const profile = useJobConsumables(makerspaceId, job.id, CONSUMABLE_ACTIONS.includes(action));
  const profileRows = activeRows(profile.data);
  const blocker = jobFormBlocker(action, values) ?? (consumableBlocker(action, profile.data, entries) || null);
  const submit = () => run.mutate({ id: job.id, action, body: jobActionBody(action, values, { hasPool, printer, entries: consumableEntries(action, profile.data, entries) }) }, {
    onSuccess: onClose,
    onError: error => {
      if (action === "accept" && errorCode(error) === "quote_required") {
        setAction("quote");
        setNotice(ACTION_ERROR_HELP.quote_required);
        run.reset();
      }
    },
  });
  const poolMachine = action === "start" ? values.machine_id : String(job.preassigned_machine_id ?? job.assigned_machine?.id ?? machines[0]?.id ?? "");
  return <Modal open title={`${TITLES[action]}: ${job.title}`} onClose={onClose}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (!blocker) submit(); }}>
      {notice ? <p role="status" className="rounded-md border border-line bg-surface p-3 text-sm">{notice}</p> : null}
      <JobActionFields action={action} values={values} set={set} machines={machines} pools={pools(poolMachine)}
        unitLabel={unitLabel} hasPool={hasPool} showOverride={action === "accept" && (code === "job_too_long" || values.override_length)} />
      {CONSUMABLE_ACTIONS.includes(action) && profileRows.length ? <section className="grid gap-2" aria-label={t`Consumables`}>
        <h3 className="title-section">{action === "quote" ? t`What the job will use` : t`What was used`}</h3>
        <EntryFields rows={action === "complete" ? profileRows.map(row => ({ ...row, required: row.required && !!profile.data?.missing_required.includes(row.key) })) : profileRows.map(row => ({ ...row, required: false }))} values={entries} onChange={setEntries} disabled={run.isPending} />
      </section> : null}
      {run.error ? <p role="alert" className="text-sm text-danger">{(code && ACTION_ERROR_HELP[code]) ?? run.error.message}
        {code && ACTION_ERROR_HELP[code] && run.error.message !== ACTION_ERROR_HELP[code] ? <span className="mt-1 block text-muted">{run.error.message}</span> : null}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        {blocker ? <p className="mr-auto self-center text-sm text-muted">{blocker}</p> : null}
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className={action === "reject" || action === "fail" ? "desk-button-danger" : "desk-button-primary"}
          disabled={!!blocker || run.isPending}>{run.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : CONFIRM[action] ?? TITLES[action]}</button>
      </div>
    </form>
  </Modal>;
}
