import { t } from "@lingui/core/macro";
import { ErrorText, StatusPill } from "../../components/ui";
import type { RestoreOperation } from "./backupApi";

export function RestoreDecision({ operation, onDecide, pending = false }: {
  operation: RestoreOperation;
  onDecide: (value: "proceed" | "reset" | "abort") => void;
  pending?: boolean;
}) {
  const waiting = operation.stage === "quiesced" && operation.decision === "pending" && operation.decision_deadline_at;
  const seconds = waiting ? Math.max(0, Math.ceil((new Date(operation.decision_deadline_at!).getTime() - Date.now()) / 1000)) : 0;
  return <section className="rounded-xl border border-danger-line bg-panel p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="title-section">{t`Restore review`}</h3><StatusPill label={operation.stage.replace(/_/g, " ")} tone="warn" /></div>
    <p className="mt-2 text-sm text-muted">{t`${operation.restore_diff.tables_compared ?? 0} tables compared; ${operation.restore_diff.tables_changed ?? 0} differ.`}</p>
    <div className="mt-4 grid max-h-72 gap-3 overflow-auto">
      {operation.restore_diff.tables?.map(table => <details key={table.table} className="rounded-control border border-line bg-surface p-3">
        <summary className="min-h-11 cursor-pointer rounded-control py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <span className="tabular-nums">{table.table}</span> {t` · ${table.live.row_count} live / ${table.archive.row_count} archived `}{table.security_relevant ? t`· security-relevant` : ""} {table.noisy ? t`· noisy` : ""}
        </summary>
        {table.row_diff ? <pre className="mt-2 overflow-auto text-xs text-muted">{JSON.stringify(table.row_diff, null, 2)}</pre> : null}
      </details>)}
    </div>
    {waiting ? <>
      <p className="mt-4 tabular-nums text-sm">{t`Decision window: ${seconds}s`}</p>
      <p className="mt-2 text-sm text-ink">{t`Proceed only after reviewing the all-table report. “Reset authority” quarantines every principal and invalidates restored credentials.`}</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button className="desk-button-primary" disabled={pending} onClick={() => onDecide("proceed")}>{pending ? t`Saving decision…` : t`Proceed`}</button>
        <button className="desk-button" disabled={pending} onClick={() => onDecide("reset")}>{t`Proceed and reset authority`}</button>
        <button className="desk-button-danger-outline" disabled={pending} onClick={() => onDecide("abort")}>{t`Abort safely`}</button>
      </div>
    </> : null}
    {operation.error_detail ? <div className="mt-4"><ErrorText message={operation.error_detail} /></div> : null}
  </section>;
}
