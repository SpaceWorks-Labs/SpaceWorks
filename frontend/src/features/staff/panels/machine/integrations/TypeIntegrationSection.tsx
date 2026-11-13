// The machine-type integration foundation (`machines.integrations`, off by default): bind the
// printer agent to this type, switch it on, and read the live status its printers report.
import { LogoLoader } from "../../../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ConfirmDialog, ErrorBlock, RelativeTime, StatusPill } from "../../../../../components/ui";
import { useIntegrationMutation, useIntegrationStatus, useTypeIntegrations, type IntegrationStatus, type TypeIntegration } from "./printerApi";

export function TypeIntegrationSection({ makerspaceId, machineTypeId }: { makerspaceId: number; machineTypeId: number }) {
  const integrations = useTypeIntegrations(makerspaceId, machineTypeId);
  const change = useIntegrationMutation(makerspaceId, machineTypeId);
  const [removing, setRemoving] = useState<TypeIntegration | null>(null);
  const rows = integrations.data ?? [];
  const live = rows.some(row => row.enabled);
  const status = useIntegrationStatus(makerspaceId, machineTypeId, live);
  return <section className="grid gap-3 rounded-xl border border-line bg-panel p-3" aria-label={t`Printer agent`}>
    <h3 className="title-panel">{t`Printer agent`}</h3>
    <p className="text-sm text-muted">{t`Lets connected printers of this type pull their approved jobs and report live status. It is created switched off.`}</p>
    {integrations.isLoading ? <LogoLoader label={t`Loading integrations…`} size={48} className="min-h-16 py-3" /> : null}
    {integrations.error ? <ErrorBlock error={integrations.error} resource={t`integrations`} onRetry={() => void integrations.refetch()} /> : null}
    {rows.map(row => <div key={row.id} className="flex flex-wrap items-center gap-3 rounded-control border border-line p-3">
      <span className="min-w-0 flex-1 text-sm font-semibold text-ink">{t`Printer agent`}</span>
      <StatusPill tone={row.enabled ? "success" : "neutral"} label={row.enabled ? t`On` : t`Off`} />
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={row.enabled}
        disabled={change.isPending} onChange={event => change.mutate({ id: row.id, enabled: event.target.checked })} />{t`Switched on`}</label>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => setRemoving(row)}>{t`Remove`}</button>
    </div>)}
    {integrations.isSuccess && !rows.length ? <div><button type="button" className="desk-button min-h-11" disabled={change.isPending}
      onClick={() => change.mutate({ create: true })}>{t`Add printer agent`}</button></div> : null}
    {change.error ? <ErrorBlock error={change.error} /> : null}
    {live ? <StatusTable rows={status.data ?? []} loading={status.isLoading} error={status.error} /> : null}
    <ConfirmDialog open={removing !== null} tone="danger" pending={change.isPending} title={t`Remove the printer agent?`}
      message={t`Printers of this type stop pulling jobs and reporting status. You can add it again later.`}
      confirmLabel={t`Remove`} onCancel={() => setRemoving(null)}
      onConfirm={() => { if (removing) change.mutate({ id: removing.id, remove: true }, { onSettled: () => setRemoving(null) }); }} />
  </section>;
}

function StatusTable({ rows, loading, error }: { rows: IntegrationStatus[]; loading: boolean; error: unknown }) {
  if (loading) return <LogoLoader label={t`Loading printer status…`} size={48} className="min-h-16 py-3" />;
  if (error) return <ErrorBlock error={error} resource={t`printer status`} />;
  if (!rows.length) return <p className="text-sm text-muted">{t`No connected printer has reported yet.`}</p>;
  return <ul className="grid gap-2" aria-label={t`Printer status`}>
    {rows.map(row => {
      const snap = row.snapshot;
      const temps = snap ? [snap.nozzle_temp_c && t`Nozzle ${snap.nozzle_temp_c} °C`, snap.bed_temp_c && t`Bed ${snap.bed_temp_c} °C`,
        snap.chamber_temp_c && t`Chamber ${snap.chamber_temp_c} °C`].filter(Boolean).join(" · ") : "";
      return <li key={row.device_id} className="grid gap-1 rounded-control border border-line p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2"><strong className="min-w-0 flex-1 text-ink">{row.device_name} · {row.machine_name}</strong>
          <StatusPill tone={snap?.state === "printing" ? "accent" : snap?.state === "error" || snap?.state === "failed" ? "danger" : "neutral"}
            label={snap ? snap.state.charAt(0).toUpperCase() + snap.state.slice(1) : t`No status yet`} /></div>
        <span className="text-muted">{row.last_seen_at ? <>{t`Last seen `}<RelativeTime date={row.last_seen_at} /></> : t`No heartbeat yet`}
          {snap?.progress_percent != null ? ` · ${snap.progress_percent}%` : ""}
          {snap?.layer_total ? ` · ${t`layer ${snap.layer_current ?? 0} of ${snap.layer_total}`}` : ""}</span>
        {temps ? <span className="text-muted">{temps}</span> : null}
        {snap?.spools.length ? <span className="text-muted">{snap.spools.map(spool =>
          `#${spool.slot} ${[spool.material, spool.colour].filter(Boolean).join(" ")}${spool.remaining_percent != null ? ` ${spool.remaining_percent}%` : ""}`).join(" · ")}</span> : null}
      </li>;
    })}
  </ul>;
}
