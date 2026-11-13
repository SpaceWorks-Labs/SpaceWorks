import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DetailDrawer, ErrorText, KeyValueCard, RelativeTime, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { ApproveRequestDialog } from "./ApproveRequestDialog";
import { CONSOLE_APPROVES_ORGANIZATIONS, controlRequestHref, hostingStatusLabels, requestedKind, useHostingDecision, useHostingRequest, type HostingRequestRow } from "./onboardingApi";
import { spaceNounTitle } from "../../../lib/spaceNoun";
import { LogoLoader } from "../../../components/LogoLoader";

function NoteDialog({ request, kind, onClose }: { request: HostingRequestRow; kind: "request-changes" | "reject"; onClose: () => void }) {
  const decision = useHostingDecision<HostingRequestRow>(request.id, kind);
  const changes = kind === "request-changes";
  return <ActionDialog title={changes ? t`Request changes` : t`Reject this request`} confirmLabel={changes ? t`Send request` : t`Reject`}
    tone={changes ? "default" : "danger"} pending={decision.isPending} error={decision.error} onCancel={onClose}
    reason={{ label: changes ? t`What should the applicant change?` : t`Reason`, min: 10, max: 2000 }}
    message={changes ? t`${request.applicant_name} gets an email with your note and a link to update the request.`
      : t`${request.applicant_name} is told the request was declined, with your reason.`}
    onSubmit={text => decision.mutate(changes ? { note: text } : { reason: text }, {
      onSuccess: () => { toast(changes ? t`Changes requested.` : t`Request rejected.`); onClose(); } })} />;
}

/** One hosting request with its revision history and the three decisions. */
export function HostingRequestDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const detail = useHostingRequest(id);
  const [dialog, setDialog] = useState<"approve" | "request-changes" | "reject" | null>(null);
  const data = detail.data;
  const open = data?.status === "submitted";
  const canApprove = open || (data?.status === "accepted" && !data.created_makerspace);
  const organization = data ? requestedKind(data) === "organization" : false;
  // Until the console route creates organization workspaces, those are approved in /control/.
  const approveHere = !organization || CONSOLE_APPROVES_ORGANIZATIONS;
  return <DetailDrawer open title={data?.space_name ?? t`Hosting request`} onClose={onClose}>
    {detail.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" /> : detail.isError ? <ErrorText resource={t`this request`} onRetry={() => { void detail.refetch(); }} /> : data ? <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill label={hostingStatusLabels()[data.status] ?? data.status} tone={data.status === "rejected" ? "danger" : data.status === "accepted" ? "success" : "warn"} />
        {canApprove && approveHere ? <button type="button" className="desk-button-primary" onClick={() => setDialog("approve")}>{t`Approve…`}</button> : null}
        {canApprove && !approveHere ? <a className="desk-button-primary" href={controlRequestHref(data.id)} target="_blank" rel="noopener noreferrer">
          {t`Approve in /control/`}<span className="sr-only">{t`(opens in a new tab)`}</span></a> : null}
        {open ? <button type="button" className="desk-button" onClick={() => setDialog("request-changes")}>{t`Request changes…`}</button> : null}
        {open || data.status === "changes_requested" ? <button type="button" className="desk-button-danger-outline" onClick={() => setDialog("reject")}>{t`Reject…`}</button> : null}
      </div>
      <KeyValueCard title={t`Request`} items={[
        { label: t`Kind`, value: spaceNounTitle(requestedKind(data)) },
        { label: t`Applicant`, value: `${data.applicant_name} · ${data.applicant_email}` },
        ...(data.applicant_phone ? [{ label: t`Phone`, value: data.applicant_phone }] : []),
        { label: t`Location`, value: data.location || t`Not given` },
        { label: t`Expected members`, value: data.expected_members ?? "Not given" },
        { label: t`Suggested address`, value: data.proposed_slug || "None" },
        { label: t`Organization`, value: data.new_organization_name || data.organization_choice || "None" },
        ...(data.space_website_url ? [{ label: t`Website`, value: data.space_website_url }] : []),
        ...(data.inviter_summary ? [{ label: t`Invited by`, value: data.inviter_summary }] : []),
        { label: t`Submitted`, value: <RelativeTime date={data.created_at} exact /> },
        ...(data.created_makerspace ? [{ label: t`Created space`, value: `${data.created_makerspace.name} (/m/${data.created_makerspace.slug})` }] : []),
      ]} />
      <section aria-labelledby="request-about" className="grid gap-2">
        <h3 id="request-about" className="title-panel">{organization ? t`About the organization` : t`About the space`}</h3>
        <p className="whitespace-pre-wrap text-sm text-ink">{data.description}</p>
      </section>
      <section aria-labelledby="request-history" className="grid gap-2">
        <h3 id="request-history" className="title-panel">{t`History`}</h3>
        {data.revisions.length ? <ol className="grid gap-3">{data.revisions.map((row, index) => <li key={index} className="rounded-xl border border-line p-3 text-sm">
          <p className="font-semibold text-ink">{row.kind === "changes_requested" ? t`Changes requested` : row.kind === "resubmitted" ? t`Resubmitted` : row.kind.replace(/_/g, " ")} · <RelativeTime date={row.created_at} /></p>
          {row.note ? <p className="mt-1 whitespace-pre-wrap text-ink">{row.note}</p> : null}
          {row.changed_fields.length ? <p className="mt-1 text-muted">{t`Changed: ${row.changed_fields.join(", ")}`}</p> : null}
        </li>)}</ol> : <p className="text-sm text-muted">{t`No revisions yet.`}</p>}
      </section>
    </div> : null}
    {data && dialog === "approve" ? <ApproveRequestDialog request={data} onClose={() => setDialog(null)} /> : null}
    {data && (dialog === "request-changes" || dialog === "reject") ? <NoteDialog request={data} kind={dialog} onClose={() => setDialog(null)} /> : null}
  </DetailDrawer>;
}
