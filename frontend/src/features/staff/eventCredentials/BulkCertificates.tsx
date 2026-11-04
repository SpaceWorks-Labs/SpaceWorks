import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { CertificatePublicationControls } from "./CertificatePublicationControls";

type Batch = { id: number; state: string; total: number; completed: number; failures: { id: number; error_code: string }[] };

export function BulkCertificates({ eventId }: { eventId: number }) {
  const [confirmed, setConfirmed] = useState(false);
  const [publish, setPublish] = useState(true);
  const [batchId, setBatchId] = useState<number | null>(null);
  const preview = useQuery({ queryKey: ["certificate-eligibility", eventId], retry: false,
    queryFn: () => staffRequest<{ eligible_count: number; event_version: number; disclosure: string }>(`/admin/events/${eventId}/certificates/eligibility/`) });
  const issue = useMutation({ mutationFn: () => staffRequest<Batch>(`/admin/events/${eventId}/certificates/bulk/`, {
    method: "POST", body: JSON.stringify({ operation_id: crypto.randomUUID(), expected_version: preview.data?.event_version,
      subjects: [], all_attended: true, confirmed_count: preview.data?.eligible_count, publish_event_details: publish }),
  }), onSuccess: (batch) => { setBatchId(batch.id); setConfirmed(false); } });
  const batch = useQuery({ queryKey: ["certificate-batch", eventId, batchId], enabled: batchId !== null, retry: false,
    queryFn: () => staffRequest<Batch>(`/admin/events/${eventId}/certificates/batches/${batchId}/`),
    refetchInterval: (query) => query.state.data?.state === "completed" || query.state.error ? false : 3000 });
  const error = preview.error || issue.error || batch.error;
  return <details className="rounded-control border border-line p-3"><summary className="min-h-11 cursor-pointer font-semibold text-ink">Bulk attendance certificates</summary>
    <div className="mt-3 grid gap-3"><p className="text-sm text-muted">Only full event managers may issue. This does not create feedback responses. Verified contribution and award subjects use the same issuance service.</p>
      {preview.data ? <>
        <p className="font-semibold text-ink">{preview.data.eligible_count} attended registrations</p>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={publish} onChange={(event) => setPublish(event.target.checked)} />Enable event/date/status public verification for this batch</label>
        <p className="text-sm text-muted">{preview.data.disclosure}</p>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />Issue to all {preview.data.eligible_count} attended registrations</label>
        <button className="desk-button-primary" type="button" disabled={!confirmed || !preview.data.eligible_count || issue.isPending} onClick={() => issue.mutate()}>Confirm bulk issue</button>
      </> : null}
      {batch.data ? <p role="status" className="text-sm text-ink">Batch {batch.data.state}: {batch.data.completed}/{batch.data.total} issued. {batch.data.failures.length} require review.</p> : null}
      {error ? <p className="text-sm text-danger" role="alert">{error.message}</p> : null}
      <button className="desk-button" type="button" onClick={() => { setConfirmed(false); void preview.refetch(); }}>Refresh eligibility</button>
      <CertificatePublicationControls eventId={eventId} />
    </div>
  </details>;
}
