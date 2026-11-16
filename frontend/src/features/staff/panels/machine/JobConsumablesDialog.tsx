import { t } from "@lingui/core/macro";
import { useState } from "react";

import { BoxArt } from "../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../components/LogoLoader";
import { Modal } from "../../../../components/ui";
import { EntryFields } from "../../../machine-consumables/EntryFields";
import { entriesPayload, entriesProblem, unitText, type EntryValues } from "../../../machine-consumables/entries";
import { useJobConsumables, useRecordJobConsumables, type ConsumableUsage } from "./jobConsumablesApi";
import type { StaffJob } from "./machineJobsApi";

function UsageList({ rows, empty }: { rows: ConsumableUsage[]; empty: string }) {
  if (!rows.length) return <p className="text-sm text-muted">{empty}</p>;
  return <ul className="grid gap-1 text-sm">{rows.map(row => <li key={row.id} className="min-w-0 break-words">
    <strong>{row.name}</strong> {row.quantity} {unitText(row.unit)}{Object.values(row.attributes ?? {}).filter(Boolean).length ? ` · ${Object.values(row.attributes).filter(Boolean).join(", ")}` : ""}</li>)}</ul>;
}

/** A job's consumables: what was estimated, what was used, and forms to record either (decision 341). */
export function JobConsumablesDialog({ job, makerspaceId, onClose }: { job: StaffJob; makerspaceId: number; onClose: () => void }) {
  const data = useJobConsumables(makerspaceId, job.id);
  const record = useRecordJobConsumables(makerspaceId, job.id);
  const [estimate, setEstimate] = useState<EntryValues>({});
  const [actual, setActual] = useState<EntryValues>({});
  const rows = (data.data?.profile ?? []).filter(row => row.is_active);
  const save = (phase: "estimate" | "actual", values: EntryValues, reset: () => void) => record.mutate({ phase, entries: entriesPayload(rows, values) }, { onSuccess: reset });
  const form = (phase: "estimate" | "actual", values: EntryValues, set: (values: EntryValues) => void) => {
    const problem = entriesProblem(rows, values, false);
    const empty = !entriesPayload(rows, values).length;
    return <div className="grid gap-3">
      <EntryFields rows={rows} values={values} onChange={set} disabled={record.isPending} />
      {problem ? <p role="status" className="text-sm text-muted">{problem}</p> : null}
      <div><button type="button" className="desk-button-primary min-h-11" disabled={!!problem || empty || record.isPending} onClick={() => save(phase, values, () => set({}))}>
        {record.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : phase === "estimate" ? t`Record estimates` : t`Record amounts used`}</button></div>
    </div>;
  };
  return <Modal open title={t`Consumables: ${job.title}`} onClose={onClose}>
    <div className="grid gap-5">
      {data.isLoading ? <LogoLoader label={t`Loading consumables…`} size={48} className="min-h-16 py-3" /> : null}
      {data.isError ? <p role="alert" className="text-sm text-danger">{data.error.message}</p> : null}
      {data.data ? <>
        {data.data.missing_required.length ? <p role="status" className="rounded-md border border-line bg-surface p-3 text-sm">{t`Still to record before the job can be completed: ${data.data.missing_required.join(", ")}`}</p> : null}
        <section className="grid gap-2"><h3 className="title-section">{t`Estimated`}</h3><UsageList rows={data.data.estimates} empty={t`Nothing estimated yet.`} /></section>
        <section className="grid gap-2"><h3 className="title-section">{t`Used`}</h3><UsageList rows={data.data.actuals} empty={t`Nothing recorded as used yet.`} /></section>
        {rows.length ? <>
          <section className="grid gap-2"><h3 className="title-section">{t`Record estimates`}</h3>{form("estimate", estimate, setEstimate)}</section>
          <section className="grid gap-2"><h3 className="title-section">{t`Record amounts used`}</h3>{form("actual", actual, setActual)}</section></> : <p className="text-sm text-muted">{t`This machine type has no consumable profile yet.`}</p>}
      </> : null}
      {record.error ? <p role="alert" className="text-sm text-danger">{record.error.message}</p> : null}
      <div className="flex justify-end border-t border-line pt-3"><button type="button" className="desk-button-ghost min-h-11" onClick={onClose}>{t`Close`}</button></div>
    </div>
  </Modal>;
}
