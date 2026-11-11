import { t } from "@lingui/core/macro";
import { DataTable, StatusPill } from "../../components/ui";
import type { OfflineQueue } from "./offlineQueueTypes";
import { kioskCommandStatusLabel, kioskOperationLabel, replayGuidance } from "./replayRecoveryGuidance";

export function KioskQueueStatus({ queue, retry, acknowledge }: {
  queue: OfflineQueue; retry: () => void; acknowledge: () => void;
}) {
  const pending = queue.commands.filter(item => !["succeeded", "failed"].includes(item.status)).length;
  const failed = queue.commands.filter(item => item.status === "failed").length;
  const complete = queue.commands.length > 0 && queue.commands.every(item => item.status === "succeeded");
  return <section className="grid gap-4" aria-label={t`Handover queue`}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="title-panel">{t`Handover queue`}</h2>
      <p className="text-sm tabular-nums" role="status">{t`${pending} pending · ${failed} failed`}</p></div>
    <DataTable data={queue.commands} getRowId={command => command.envelope.client_command_id}
      emptyTitle={t`No handovers queued.`} emptyDescription={t`Captured handovers will appear here until the server confirms them.`}
      columns={[
        { key: "sequence", header: t`Sequence`, render: command => t`Sequence ${command.envelope.sequence}` },
        { key: "operation", header: t`Operation`, render: command => kioskOperationLabel(command.envelope.kind) },
        { key: "status", header: t`Status`, render: command => <StatusPill label={kioskCommandStatusLabel(command.status)}
          tone={command.status === "failed" ? "danger" : command.status === "succeeded" ? "success" : "warn"} /> },
        { key: "review", header: t`Next step`, render: command => command.status === "failed" ? <div className="grid gap-2">
          <p>{replayGuidance(command.lastFailure)}</p>{command.result?.replay_id
            ? <a className="desk-button" href={`${window.location.pathname}?recovery=${encodeURIComponent(command.result.replay_id)}`}>{t`Review failed handover online`}</a>
            : <p>{t`No server recovery record was confirmed. Keep this local evidence for staff review.`}</p>}
        </div> : <span className="text-sm text-muted">{command.status === "succeeded" ? t`Recorded by the server` : t`Waiting for server confirmation`}</span> },
      ]} />
    {failed ? <p className="text-sm text-danger">{t`Failed work needs staff review. Other handovers can continue.`}</p> : null}
    <div className="flex flex-wrap gap-3"><button type="button" className="desk-button" onClick={retry}>{t`Retry queued work`}</button>
      {complete ? <button type="button" className="desk-button" onClick={acknowledge}>{t`Acknowledge completion and clear local work`}</button> : null}</div>
  </section>;
}
