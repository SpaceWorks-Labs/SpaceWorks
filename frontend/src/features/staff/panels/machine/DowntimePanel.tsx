import { formatLocale } from "../../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, StatCard, StatusPill } from "../../../../components/ui";
import { localInputValue, useMachineDowntime, useMachineLockout, useUpdateDowntime, type DowntimePeriod } from "./machineDowntimeApi";

const when = (iso: string | null) => iso ? new Date(iso).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" }) : "";

/** Header badge: shown only while overdue blocking maintenance locks the machine out. */
export function LockoutBadge({ machineId }: { machineId: number }) {
  const lockout = useMachineLockout(machineId);
  return lockout.data?.locked ? <StatusPill tone="danger" label={t`Locked out`} /> : null;
}

/** Why a machine is blocked: the overdue schedules that lock it out (`blocks_use`). */
export function LockoutNotice({ machineId }: { machineId: number }) {
  const lockout = useMachineLockout(machineId);
  if (!lockout.data?.locked) return lockout.error ? <ErrorBlock error={lockout.error} resource="lockout state" /> : null;
  return <section className="grid gap-2 rounded-xl border border-line bg-surface p-3" aria-label={t`Lockout`}>
    <StatusPill tone="danger" label={t`Locked out`} />
    <p className="text-sm">{t`Jobs cannot start on this machine until this overdue maintenance is done:`}</p>
    <ul className="grid gap-1 text-sm">{lockout.data.schedules.map(row => <li key={row.id}>{t`${row.description} · due ${new Date(`${row.next_due}T00:00:00`).toLocaleDateString(formatLocale())}`}</li>)}</ul>
  </section>;
}

/** Uptime, mean time to repair and the downtime periods (maintenance and offline), with the open period editable. */
export function DowntimePanel({ machineId, canEdit }: { machineId: number; canEdit: boolean }) {
  const downtime = useMachineDowntime(machineId);
  if (downtime.error) return <ErrorBlock error={downtime.error} resource="downtime" onRetry={() => { void downtime.refetch(); }} />;
  if (!downtime.data) return downtime.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading downtime…`}</p> : null;
  const { summary, periods } = downtime.data;
  return <section className="grid gap-3" aria-labelledby={`downtime-${machineId}`}>
    <h3 id={`downtime-${machineId}`} className="title-section">{t`Downtime`}</h3>
    <div className="grid gap-3 sm:grid-cols-2">
      <StatCard label={t`Uptime, last ${summary.days} days`} value={`${summary.uptime_percent.toFixed(1)}%`} />
      <StatCard label={t`Average time to repair`} value={summary.mean_hours_to_repair === null ? "No repairs yet" : `${summary.mean_hours_to_repair.toFixed(1)} h`} />
    </div>
    {!periods.length ? <p className="text-sm text-muted">{t`No downtime recorded.`}</p> : <ul className="grid gap-2">{periods.map(period =>
      <li key={period.id} className="grid gap-2 rounded-xl border border-line p-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={period.ended_at ? "neutral" : "warn"} label={`${period.kind === "offline" ? "Offline" : "Maintenance"}${period.ended_at ? "" : " now"}`} />
          <span className="text-sm text-muted">{when(period.started_at)}{period.ended_at ? ` to ${when(period.ended_at)}` : ""}</span>
        </div>
        {!period.ended_at && canEdit ? <OpenPeriodForm key={period.id} machineId={machineId} period={period} /> : <>
          {period.reason ? <p className="text-sm">{period.reason}</p> : null}
          {period.expected_back_at && !period.ended_at ? <p className="text-sm text-muted">{t`Expected back ${when(period.expected_back_at)}`}</p> : null}
        </>}
      </li>)}</ul>}
  </section>;
}

function OpenPeriodForm({ machineId, period }: { machineId: number; period: DowntimePeriod }) {
  const update = useUpdateDowntime(machineId);
  const [reason, setReason] = useState(period.reason);
  const [back, setBack] = useState(localInputValue(period.expected_back_at));
  return <form className="grid gap-2 sm:grid-cols-2" onSubmit={event => { event.preventDefault();
    update.mutate({ reason: reason.trim(), expected_back_at: back ? new Date(back).toISOString() : null }); }}>
    <label className="eyebrow grid gap-1">{t`Reason`}<input className="desk-input" maxLength={300} value={reason} onChange={event => setReason(event.target.value)} /></label>
    <label className="eyebrow grid gap-1">{t`Expected back`}<input className="desk-input w-full min-w-0" type="datetime-local" value={back} onChange={event => setBack(event.target.value)} /></label>
    <button className="desk-button-primary w-fit" disabled={update.isPending}>{update.isPending ? t`Saving…` : t`Save downtime`}</button>
    {update.isSuccess ? <p role="status" className="self-center text-sm">{t`Saved.`}</p> : null}
    {update.error ? <p role="alert" className="text-sm text-danger sm:col-span-2">{update.error.message}</p> : null}
  </form>;
}
