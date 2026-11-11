import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorBlock, ListRow, StatusPill } from "../../../components/ui";
import { staffRequest, StructuredApiError } from "../../../lib/api";
import { useServiceState, type SubjectType } from "../repairs/repairsApi";

/** One machine (or other subject) the viewer may switch, hand-typed from `GET service-state` (decision 242, MC6). */
export type ServiceStateRow = {
  subject_type: SubjectType; subject_id: number; name: string; machine_type: string | null; status: string; in_service: boolean;
};

/**
 * MC6: take a covered machine out of service, or bring it back, without first opening a repair
 * job (`issue_id` is optional on the server). The server lists only what this person covers.
 */
export function ServiceStateList({ makerspaceId }: { makerspaceId: number }) {
  const rows = useQuery({ queryKey: ["service-state", makerspaceId], retry: false,
    queryFn: ({ signal }) => staffRequest<ServiceStateRow[]>(`/admin/makerspaces/${makerspaceId}/service-state`, { signal }) });
  const change = useServiceState(makerspaceId);
  const [taking, setTaking] = useState<ServiceStateRow | null>(null);
  const [reason, setReason] = useState("");
  const status = rows.error instanceof StructuredApiError ? rows.error.status : undefined;
  if (status === 403 || status === 404) return null;
  const key = (row: ServiceStateRow) => `${row.subject_type}:${row.subject_id}`;
  const submit = (row: ServiceStateRow, inService: boolean, why = "") => change.mutate(
    { subject_type: row.subject_type, subject_id: row.subject_id, in_service: inService, ...(why ? { reason: why } : {}) },
    { onSuccess: () => { setTaking(null); setReason(""); void rows.refetch(); } });
  const list = rows.data ?? [];
  return <section className="grid min-w-0 gap-3" aria-labelledby="service-state-title">
    <div><h2 id="service-state-title" className="title-panel">{t`In service`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Take a machine out of service while it is unsafe or being fixed. Bookings and jobs on it are held until it is back.`}</p></div>
    {rows.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading machines…`}</p> : null}
    {rows.isError ? <ErrorBlock error={rows.error} onRetry={() => { void rows.refetch(); }} /> : null}
    {rows.isSuccess && !list.length ? <p className="text-sm text-muted">{t`Nothing here for you to switch. Machines in your coverage appear here.`}</p> : null}
    <div className="grid gap-2">{list.map(row => <div key={key(row)} className="grid gap-2">
      <ListRow title={row.name} meta={row.machine_type ?? undefined}
        right={<span className="flex flex-wrap items-center gap-2">
          <StatusPill tone={row.in_service ? "success" : "danger"} label={row.in_service ? t`In service` : t`Out of service`} />
          {row.in_service
            ? <button type="button" className="desk-button min-h-11" disabled={change.isPending} onClick={() => { setTaking(row); setReason(""); }}>{t`Take out of service`}</button>
            : <button type="button" className="desk-button min-h-11" disabled={change.isPending} onClick={() => submit(row, true)}>{t`Back in service`}</button>}
        </span>} />
      {taking && key(taking) === key(row) ? <form className="grid gap-2 rounded-control border border-line p-3" onSubmit={event => { event.preventDefault(); if (reason.trim()) submit(row, false, reason.trim()); }}>
        <label className="grid gap-1 text-sm font-semibold">{t`Why is ${row.name} out of service?`}
          <input className="desk-input" required value={reason} onChange={event => setReason(event.target.value)} /></label>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="desk-button-danger min-h-11" disabled={!reason.trim() || change.isPending}>{t`Take out of service`}</button>
          <button type="button" className="desk-button min-h-11" onClick={() => setTaking(null)}>{t`Cancel`}</button>
        </div>
      </form> : null}
    </div>)}</div>
    {change.error ? <ErrorBlock error={change.error} /> : null}
  </section>;
}
