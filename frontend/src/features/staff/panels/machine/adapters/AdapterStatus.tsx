import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { RelativeTime, StatusPill } from "../../../../../components/ui";
import { ProgressBar } from "../../../../../components/ui/ProgressBar";
import { AdapterConfig } from "./AdapterConfig";
import { AdapterControls } from "./AdapterControls";
import { AdapterJobs } from "./AdapterJobs";
import { stateLabel, stateTone, targetTypeLabel } from "./adapterCopy";
import { adapterKeys, adaptersApi, type AdapterSummary, type Binding, type BindingStatus } from "./adaptersApi";
import { useTargetLabel } from "./bindingTargets";

/** Temperatures and readings the bridge reported in `telemetry` (`status.item.json`). */
export const temperatures = (status: BindingStatus): [string, number][] => Object.entries(status.telemetry?.temperatures ?? {}).filter(([, value]) => Number.isFinite(value));
export const readings = (status: BindingStatus): [string, number][] => Object.entries(status.telemetry?.metrics ?? {}).filter(([, value]) => Number.isFinite(value));
const humanKey = (key: string) => key.replace(/_/g, " ");
/** `observed_at` arrives as an ISO time, or as epoch seconds when it comes straight from the bridge's report. */
export const observedIso = (value: string | number) => typeof value === "number" ? new Date(value * 1000).toISOString() : value;
export function eta(status: BindingStatus): string {
  const seconds = status.eta_seconds;
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return "";
  const minutes = Math.round(seconds / 60);
  return minutes < 1 ? t`under a minute left` : minutes < 90 ? t`about ${minutes} min left` : t`about ${Math.round(minutes / 6) / 10} hours left`;
}
/** Interlocks that are NOT safe, in words. */
export function openInterlocks(status: BindingStatus): string[] {
  const row = status.interlocks ?? {};
  return [...(row.enclosure_closed === false ? [t`Enclosure open`] : []), ...(row.estop_ok === false ? [t`Emergency stop pressed`] : []),
    ...(row.filter_ok === false ? [t`Filter needs attention`] : [])];
}

type RecentEvent = { id: string; event_type: string; observed_at: string };

function BindingStatusCard({ binding, name, makerspaceId, adapterId, disabled, recent }: {
  binding: Binding; name: string; makerspaceId: number; adapterId: string; disabled: boolean; recent: RecentEvent[];
}) {
  const status = binding.status;
  const temps = status ? temperatures(status) : [];
  const percent = typeof status?.progress_percent === "number" ? status.progress_percent : null;
  return <article className="grid gap-3 rounded-2xl border border-line bg-panel p-4" aria-label={name}>
    <header className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1"><h3 className="title-section break-words">{name}</h3>
        <p className="text-sm text-muted">{targetTypeLabel(binding.target_type)}{binding.enabled ? "" : ` · ${t`Disabled`}`}</p></div>
      <StatusPill label={stateLabel(status?.state)} tone={stateTone(status?.state)} />
    </header>
    {status ? <div className="grid gap-3">
      {percent !== null ? <div className="grid gap-1"><ProgressBar value={percent / 100} label={t`Progress of ${name}`} />
        <p className="text-sm text-muted">{t`${Math.round(percent)}% done`}{eta(status) ? ` · ${eta(status)}` : ""}</p></div> : null}
      {temps.length ? <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">{temps.map(([key, value]) => <div key={key} className="flex gap-1">
        <dt className="text-muted">{humanKey(key)}</dt><dd className="tabular-nums">{value}°C</dd></div>)}</dl> : null}
      {status.error_codes?.length ? <ul className="flex flex-wrap gap-2" aria-label={t`Errors`}>{status.error_codes.map(code =>
        <li key={code}><StatusPill label={code} tone="danger" /></li>)}</ul> : null}
      {status.error_detail ? <p className="text-sm text-danger">{status.error_detail}</p> : null}
      {openInterlocks(status).length ? <p className="text-sm text-danger">{openInterlocks(status).join(" · ")}</p> : null}
      {readings(status).length ? <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">{readings(status).map(([key, value]) => <div key={key} className="flex gap-1">
        <dt className="text-muted">{humanKey(key)}</dt><dd className="tabular-nums">{value}</dd></div>)}</dl> : null}
      <p className="text-xs text-muted">{status.power === "on" ? `${t`Power on`} · ` : status.power === "off" ? `${t`Power off`} · ` : ""}
        {status.area_clear === false ? `${t`Work area not clear`} · ` : ""}{t`Reported `}<RelativeTime date={observedIso(status.observed_at)} /></p>
    </div> : <p className="text-sm text-muted">{t`The bridge has not reported on this target yet.`}</p>}
    {recent.length ? <details className="text-sm"><summary className="cursor-pointer font-semibold">{t`Last events`}</summary>
      <ul className="mt-2 grid gap-1">{recent.map(event => <li key={event.id} className="flex flex-wrap gap-2 text-muted"><span>{event.event_type}</span><RelativeTime date={event.observed_at} /></li>)}</ul></details> : null}
    <AdapterControls makerspaceId={makerspaceId} adapterId={adapterId} binding={binding} name={name} disabled={disabled} />
    {binding.capabilities.includes("control") ? <AdapterConfig makerspaceId={makerspaceId} binding={binding} name={name} disabled={disabled} /> : null}
    {binding.capabilities.includes("job.dispatch") && binding.machine_id !== null ? <AdapterJobs makerspaceId={makerspaceId} binding={binding} disabled={disabled} /> : null}
  </article>;
}

/** The normalised state of every bound target (polled every 10 s by the detail query; there is no push). */
export function AdapterStatus({ makerspaceId, adapter, disabled }: { makerspaceId: number; adapter: AdapterSummary; disabled: boolean }) {
  const label = useTargetLabel(makerspaceId, adapter.bindings);
  const events = useQuery({ queryKey: adapterKeys.events(makerspaceId, adapter.id), queryFn: () => adaptersApi.events(adapter.id), refetchInterval: 30_000 });
  if (!adapter.bindings.length) return <p className="text-sm text-muted">{t`Nothing is bound to this adapter yet. Use the Bindings tab to choose what it controls.`}</p>;
  return <div className="grid gap-4">{adapter.bindings.map(binding => <BindingStatusCard key={binding.id} binding={binding} makerspaceId={makerspaceId}
    adapterId={adapter.id} disabled={disabled} name={label(binding.target_type, binding.machine_id, binding.target_id, binding.external_ref)}
    recent={(events.data ?? []).filter(event => event.binding === binding.id).slice(0, 3)} />)}</div>;
}
