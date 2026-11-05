import { useState } from "react";
import { DetailDrawer, ErrorText, KeyValueCard, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { ApproveRequestDialog } from "./ApproveRequestDialog";
import { HOSTING_STATUS_LABELS, useHostingDecision, useHostingRequest, type HostingRequestRow } from "./onboardingApi";

function NoteDialog({ request, kind, onClose }: { request: HostingRequestRow; kind: "request-changes" | "reject"; onClose: () => void }) {
  const decision = useHostingDecision<HostingRequestRow>(request.id, kind);
  const changes = kind === "request-changes";
  return <ActionDialog title={changes ? "Request changes" : "Reject this request"} confirmLabel={changes ? "Send request" : "Reject"}
    tone={changes ? "default" : "danger"} pending={decision.isPending} error={decision.error} onCancel={onClose}
    reason={{ label: changes ? "What should the applicant change?" : "Reason", min: 10, max: 2000 }}
    message={changes ? `${request.applicant_name} gets an email with your note and a link to update the request.`
      : `${request.applicant_name} is told the request was declined, with your reason.`}
    onSubmit={text => decision.mutate(changes ? { note: text } : { reason: text }, {
      onSuccess: () => { toast(changes ? "Changes requested." : "Request rejected."); onClose(); } })} />;
}

/** One hosting request with its revision history and the three decisions. */
export function HostingRequestDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const detail = useHostingRequest(id);
  const [dialog, setDialog] = useState<"approve" | "request-changes" | "reject" | null>(null);
  const data = detail.data;
  const open = data?.status === "submitted";
  const canApprove = open || (data?.status === "accepted" && !data.created_makerspace);
  return <DetailDrawer open title={data?.space_name ?? "Hosting request"} onClose={onClose}>
    {detail.isLoading ? <Skeleton className="h-40 w-full" /> : detail.isError ? <ErrorText resource="this request" onRetry={() => { void detail.refetch(); }} /> : data ? <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill label={HOSTING_STATUS_LABELS[data.status] ?? data.status} tone={data.status === "rejected" ? "danger" : data.status === "accepted" ? "success" : "warn"} />
        {canApprove ? <button type="button" className="desk-button-primary" onClick={() => setDialog("approve")}>Approve…</button> : null}
        {open ? <button type="button" className="desk-button" onClick={() => setDialog("request-changes")}>Request changes…</button> : null}
        {open || data.status === "changes_requested" ? <button type="button" className="desk-button-danger-outline" onClick={() => setDialog("reject")}>Reject…</button> : null}
      </div>
      <KeyValueCard title="Request" items={[
        { label: "Applicant", value: `${data.applicant_name} · ${data.applicant_email}` },
        ...(data.applicant_phone ? [{ label: "Phone", value: data.applicant_phone }] : []),
        { label: "Location", value: data.location },
        { label: "Expected members", value: data.expected_members ?? "Not given" },
        { label: "Suggested address", value: data.proposed_slug || "None" },
        { label: "Organization", value: data.new_organization_name || data.organization_choice || "None" },
        ...(data.space_website_url ? [{ label: "Website", value: data.space_website_url }] : []),
        ...(data.inviter_summary ? [{ label: "Invited by", value: data.inviter_summary }] : []),
        { label: "Submitted", value: <RelativeTime date={data.created_at} exact /> },
        ...(data.created_makerspace ? [{ label: "Created space", value: `${data.created_makerspace.name} (/m/${data.created_makerspace.slug})` }] : []),
      ]} />
      <section aria-labelledby="request-about" className="grid gap-2">
        <h3 id="request-about" className="title-panel">About the space</h3>
        <p className="whitespace-pre-wrap text-sm text-ink">{data.description}</p>
      </section>
      <section aria-labelledby="request-history" className="grid gap-2">
        <h3 id="request-history" className="title-panel">History</h3>
        {data.revisions.length ? <ol className="grid gap-3">{data.revisions.map((row, index) => <li key={index} className="rounded-xl border border-line p-3 text-sm">
          <p className="font-semibold text-ink">{row.kind === "changes_requested" ? "Changes requested" : row.kind === "resubmitted" ? "Resubmitted" : row.kind.replace(/_/g, " ")} · <RelativeTime date={row.created_at} /></p>
          {row.note ? <p className="mt-1 whitespace-pre-wrap text-ink">{row.note}</p> : null}
          {row.changed_fields.length ? <p className="mt-1 text-muted">Changed: {row.changed_fields.join(", ")}</p> : null}
        </li>)}</ol> : <p className="text-sm text-muted">No revisions yet.</p>}
      </section>
    </div> : null}
    {data && dialog === "approve" ? <ApproveRequestDialog request={data} onClose={() => setDialog(null)} /> : null}
    {data && (dialog === "request-changes" || dialog === "reject") ? <NoteDialog request={data} kind={dialog} onClose={() => setDialog(null)} /> : null}
  </DetailDrawer>;
}
