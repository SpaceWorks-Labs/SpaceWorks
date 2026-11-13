import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { ApiKeyApproveDialog } from "./ApiKeyApproveDialog";
import { QueueDecisionDialog } from "./QueueDecisionDialog";
import { QUEUE_TONES, QueueList } from "./QueueList";
import type { ApiKeyRequest, ArchiveRequest, SubdomainRequest } from "./requestsApi";

const archiveStatuses = () => ({ pending: t`Waiting`, approved: t`Approved`, declined: t`Declined`, withdrawn: t`Withdrawn` });
const decidedStatuses = () => ({ pending: t`Waiting`, approved: t`Approved`, rejected: t`Rejected` });
const label = (statuses: Record<string, string>, status: string) => statuses[status] ?? status;

type Acting =
  | { kind: "archive"; row: ArchiveRequest; decision: "approve" | "decline" }
  | { kind: "api-key"; row: ApiKeyRequest; decision: "approve" | "reject" }
  | { kind: "subdomain"; row: SubdomainRequest; decision: "approve" | "reject" };

function Decide({ status, name, onApprove, onRefuse, refuse = t`Reject` }: { status: string; name: string; onApprove: () => void; onRefuse: () => void; refuse?: string }) {
  return <div className="flex flex-wrap items-center gap-2">
    <StatusPill label={label({ ...archiveStatuses(), ...decidedStatuses() }, status)} tone={QUEUE_TONES[status] ?? "neutral"} />
    {status === "pending" ? <>
      <button type="button" className="desk-button" aria-label={t`Approve ${name}`} onClick={onApprove}>{t`Approve…`}</button>
      <button type="button" className="desk-button-danger-outline" aria-label={t`${refuse} ${name}`} onClick={onRefuse}>{t`${refuse}…`}</button>
    </> : null}
  </div>;
}

function ActingDialog({ acting, onClose }: { acting: Acting; onClose: () => void }) {
  if (acting.kind === "api-key" && acting.decision === "approve") return <ApiKeyApproveDialog row={acting.row} onClose={onClose} />;
  if (acting.kind === "archive") {
    return acting.decision === "approve"
      ? <QueueDecisionDialog kind="archive-requests" id={acting.row.id} decision="approve" title={t`Approve this archive request`} confirm={t`Archive space`}
        danger note="optional" done={t`Space archived.`} onClose={onClose}
        message={t`Approving archives ${acting.row.makerspace_name} now. Members and staff lose access; its data is kept.`} />
      : <QueueDecisionDialog kind="archive-requests" id={acting.row.id} decision="decline" title={t`Decline this archive request`} confirm={t`Decline request`}
        note="required" done={t`Archive request declined.`} onClose={onClose}
        message={t`${acting.row.makerspace_name} stays as it is. The note is recorded with the decision.`} />;
  }
  if (acting.kind === "api-key") {
    return <QueueDecisionDialog kind="api-key-requests" id={acting.row.id} decision="reject" title={t`Reject this API key request`} confirm={t`Reject request`}
      danger done={t`API key request rejected.`} onClose={onClose} message={t`No API client is issued to ${acting.row.makerspace_name} for "${acting.row.label}".`} />;
  }
  return acting.decision === "approve"
    ? <QueueDecisionDialog kind="subdomain-requests" id={acting.row.id} decision="approve" title={t`Approve this web address`} confirm={t`Approve address`}
      done={t`Web address approved.`} onClose={onClose}
      message={t`Gives ${acting.row.makerspace_name} the address "${acting.row.requested_label}" now, with its certificate.`} />
    : <QueueDecisionDialog kind="subdomain-requests" id={acting.row.id} decision="reject" title={t`Reject this web address`} confirm={t`Reject address`}
      danger done={t`Web address rejected.`} onClose={onClose} message={t`${acting.row.makerspace_name} keeps its current address.`} />;
}

/** The three platform request queues that used to be decided only in /control/. */
export function RequestsSection() {
  const [acting, setActing] = useState<Acting | null>(null);
  return <div className="grid gap-6">
    <QueueList<ArchiveRequest> kind="archive-requests" title={t`Archive requests`} resource={t`archive requests`} statuses={archiveStatuses()}
      renderRow={row => <ListRow title={row.makerspace_name}
        meta={<>{t`asked `}<RelativeTime date={row.requested_at} exact />{row.reason ? t` · "${row.reason}"` : ""}
          {row.resolved_at ? <> {t` · decided `}<RelativeTime date={row.resolved_at} exact /></> : null}
          {row.resolution_note ? t` · note: "${row.resolution_note}"` : ""}</>}
        right={<Decide status={row.status} name={t`the archive request of ${row.makerspace_name}`} refuse={t`Decline`}
          onApprove={() => setActing({ kind: "archive", row, decision: "approve" })} onRefuse={() => setActing({ kind: "archive", row, decision: "decline" })} />} />} />
    <QueueList<ApiKeyRequest> kind="api-key-requests" title={t`API key requests`} resource={t`API key requests`} statuses={decidedStatuses()}
      renderRow={row => <ListRow title={row.label}
        meta={<>{t`${row.makerspace_name} · asked `}<RelativeTime date={row.created_at} exact />{row.reason ? t` · "${row.reason}"` : ""}
          {row.allowed_origins.length ? t` · origins: ${row.allowed_origins.join(", ")}` : t` · no origins`}
          {row.resolved_at ? <> {t` · decided `}<RelativeTime date={row.resolved_at} exact /></> : null}</>}
        right={<Decide status={row.status} name={t`the API key "${row.label}" for ${row.makerspace_name}`}
          onApprove={() => setActing({ kind: "api-key", row, decision: "approve" })} onRefuse={() => setActing({ kind: "api-key", row, decision: "reject" })} />} />} />
    <QueueList<SubdomainRequest> kind="subdomain-requests" title={t`Web address requests`} resource={t`web address requests`} statuses={decidedStatuses()}
      renderRow={row => <ListRow title={row.requested_label}
        meta={<>{t`${row.makerspace_name} · asked `}<RelativeTime date={row.created_at} exact />
          {row.decided_at ? <> {t` · decided `}<RelativeTime date={row.decided_at} exact /></> : null}</>}
        right={<Decide status={row.status} name={t`the address ${row.requested_label} for ${row.makerspace_name}`}
          onApprove={() => setActing({ kind: "subdomain", row, decision: "approve" })} onRefuse={() => setActing({ kind: "subdomain", row, decision: "reject" })} />} />} />
    {acting ? <ActingDialog acting={acting} onClose={() => setActing(null)} /> : null}
  </div>;
}
