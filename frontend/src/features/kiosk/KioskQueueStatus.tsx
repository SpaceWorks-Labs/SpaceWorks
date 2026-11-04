import { DataTable, StatusPill } from "../../components/ui";
import type { OfflineQueue } from "./offlineQueueTypes";
import { replayGuidance } from "./replayRecoveryGuidance";

export function KioskQueueStatus({ queue, retry, acknowledge }: {
  queue: OfflineQueue; retry: () => void; acknowledge: () => void;
}) {
  const pending = queue.commands.filter(item => !["succeeded", "failed"].includes(item.status)).length;
  const failed = queue.commands.filter(item => item.status === "failed").length;
  const complete = queue.commands.length > 0 && queue.commands.every(item => item.status === "succeeded");
  return <section className="grid gap-4" aria-label="Handover queue">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="title-panel">Handover queue</h2>
      <p className="text-sm tabular-nums" role="status">{pending} pending · {failed} failed</p></div>
    <DataTable data={queue.commands} getRowId={command => command.envelope.client_command_id}
      emptyTitle="No handovers queued." emptyDescription="Captured handovers will appear here until the server confirms them."
      columns={[
        { key: "sequence", header: "Sequence", render: command => `Sequence ${command.envelope.sequence}` },
        { key: "operation", header: "Operation", render: command => command.envelope.kind.replace(/_/g, " ") },
        { key: "status", header: "Status", render: command => <StatusPill label={command.status === "queued" ? "Queued" : command.status === "succeeded" ? "Confirmed" : command.status.replace(/^./, c => c.toUpperCase())}
          tone={command.status === "failed" ? "danger" : command.status === "succeeded" ? "success" : "warn"} /> },
        { key: "review", header: "Next step", render: command => command.status === "failed" ? <div className="grid gap-2">
          <p>{replayGuidance(command.lastFailure)}</p>{command.result?.replay_id
            ? <a className="desk-button" href={`${window.location.pathname}?recovery=${encodeURIComponent(command.result.replay_id)}`}>Review failed handover online</a>
            : <p>No server recovery record was confirmed. Keep this local evidence for staff review.</p>}
        </div> : <span className="text-sm text-muted">{command.status === "succeeded" ? "Recorded by the server" : "Waiting for server confirmation"}</span> },
      ]} />
    {failed ? <p className="text-sm text-danger">Failed work needs staff review. Other handovers can continue.</p> : null}
    <div className="flex flex-wrap gap-3"><button type="button" className="desk-button" onClick={retry}>Retry queued work</button>
      {complete ? <button type="button" className="desk-button" onClick={acknowledge}>Acknowledge completion and clear local work</button> : null}</div>
  </section>;
}
