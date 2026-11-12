import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { BoxArt } from "../../components/BoxSpinner";
import { Callout } from "../../components/ui";
import { EntryFields } from "../machine-consumables/EntryFields";
import { entriesPayload, entriesProblem, unitText, type EntryValues } from "../machine-consumables/entries";
import { jobErrorMessage, reportJobConsumables } from "./api";
import type { MemberJob } from "./types";

/**
 * Decision 341: the member reports what their own job used, for the consumables the machine type lets members
 * report. Each one is recorded once; recorded ones show their amount instead of a field.
 */
export function JobConsumablesReportCard({ job, onUpdated }: { job: Pick<MemberJob, "id" | "report_consumables">; onUpdated: () => void }) {
  const rows = job.report_consumables ?? [];
  const open = rows.filter(row => row.recorded_quantity === null);
  const [values, setValues] = useState<EntryValues>({});
  const send = useMutation({
    mutationFn: () => reportJobConsumables(job.id, entriesPayload(open, values)),
    onSuccess: () => { setValues({}); onUpdated(); },
  });
  if (!rows.length) return null;
  const problem = entriesProblem(open, values, false);
  const nothing = entriesPayload(open, values).length === 0;
  return <section className="desk-panel grid gap-4 p-5" aria-labelledby="job-consumables-title">
    <div><h2 id="job-consumables-title" className="title-panel">{t`What your job used`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Tell the space how much you used. Each amount is recorded once.`}</p></div>
    {rows.some(row => row.recorded_quantity !== null) ? <ul className="grid gap-1 text-sm">
      {rows.filter(row => row.recorded_quantity !== null).map(row => <li key={row.key}>
        <span className="font-semibold text-ink">{row.name}</span>: {row.recorded_quantity} {unitText(row.unit)}</li>)}
    </ul> : null}
    {open.length ? <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (!problem && !nothing) send.mutate(); }}>
      <EntryFields rows={open} values={values} onChange={setValues} disabled={send.isPending} />
      {problem ? <p role="alert" className="text-sm text-danger">{problem}</p> : null}
      {send.isError ? <Callout size="inline" tone="danger" lead={jobErrorMessage(send.error)} /> : null}
      <button type="submit" className="desk-button-brand justify-self-start" disabled={send.isPending || Boolean(problem) || nothing}>
        {send.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Report use`}</button>
    </form> : null}
  </section>;
}
