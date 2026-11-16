import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Field, RelativeTime, StatusPill } from "../../../../../components/ui";
import { MultiLineChart } from "../../charts/MultiLineChart";
import type { ChartData } from "../../charts/chartSpec";
import { ArtifactGallery, artifactKindLabel } from "./ArtifactGallery";
import { adapterErrorMessage } from "./adapterCopy";
import type { AdapterSummary, Binding } from "./adaptersApi";
import { mediaApi, mediaKeys, type Detection, type DetectionKind, type Telemetry } from "./adaptersMediaApi";
import { useTargetLabel } from "./bindingTargets";

const withCapability = (adapter: AdapterSummary, name: string) => adapter.bindings.filter(row => row.capabilities.includes(name));

/** One select for the bindings of an adapter that serve a capability; returns the chosen binding. */
function useBindingPick(makerspaceId: number, rows: Binding[]) {
  const label = useTargetLabel(makerspaceId, rows);
  const [picked, setPicked] = useState("");
  const binding = rows.find(row => row.id === picked) ?? rows[0];
  const select = rows.length > 1 ? <Field label={t`Target`}><select className="desk-input" value={binding?.id ?? ""} onChange={event => setPicked(event.target.value)}>
    {rows.map(row => <option key={row.id} value={row.id}>{label(row.target_type, row.machine_id, row.target_id, row.external_ref)}</option>)}</select></Field> : null;
  return { binding, select };
}

const KINDS = ["", "timelapse", "thumbnail", "preview", "failure_snapshot"] as const;

/** Timelapses, job previews and failure snapshots a device uploaded (decision 321b): private, retention-limited. */
export function AdapterArtifacts({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const { binding, select } = useBindingPick(makerspaceId, withCapability(adapter, "artifact.upload"));
  const [kind, setKind] = useState("");
  const list = useQuery({ queryKey: mediaKeys.artifacts(binding?.id ?? "", kind), queryFn: () => mediaApi.artifacts(binding!.id, kind), enabled: Boolean(binding) });
  if (!binding) return <p className="text-sm text-muted">{t`No target on this adapter uploads files.`}</p>;
  return <div className="grid gap-4">
    {select}
    <Field label={t`Kind`}><select className="desk-input" value={kind} onChange={event => setKind(event.target.value)}>
      {KINDS.map(value => <option key={value} value={value}>{value ? artifactKindLabel(value) : t`All kinds`}</option>)}</select></Field>
    {list.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(list.error)}</p> : <ArtifactGallery rows={list.data?.results ?? []} getUrl={mediaApi.artifactUrl} />}
  </div>;
}

export function detectionKindLabel(kind: DetectionKind | string): string {
  switch (kind) {
    case "failure": return t`Print failure`;
    case "spaghetti": return t`Spaghetti`;
    case "fire": return t`Fire`;
    case "smoke": return t`Smoke`;
    case "person": return t`Person`;
    default: return t`Other`;
  }
}
export const detectionTone = (kind: DetectionKind | string) => kind === "fire" || kind === "smoke" ? "danger" as const : kind === "failure" || kind === "spaghetti" ? "warn" as const : "neutral" as const;

export function DetectionList({ rows }: { rows: Detection[] }) {
  if (!rows.length) return <p className="text-sm text-muted">{t`No detections.`}</p>;
  return <ul className="grid gap-2" aria-label={t`Detections`}>{rows.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-panel p-3">
    <StatusPill label={detectionKindLabel(row.kind)} tone={detectionTone(row.kind)} />
    <span className="text-sm tabular-nums">{t`${Math.round(row.confidence * 100)}% sure`}</span>
    <span className="text-sm text-muted"><RelativeTime date={row.observed_at} /></span>
    {row.note ? <span className="text-sm">{row.note}</span> : null}
  </li>)}</ul>;
}

/** Alerts a device raised. Core only tells people; it never pauses or stops anything on its own. */
export function AdapterDetections({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const { binding, select } = useBindingPick(makerspaceId, withCapability(adapter, "detection.report"));
  const list = useQuery({ queryKey: mediaKeys.detections(binding?.id ?? ""), queryFn: () => mediaApi.detections(binding!.id), enabled: Boolean(binding), refetchInterval: 15_000 });
  if (!binding) return <p className="text-sm text-muted">{t`No target on this adapter reports detections.`}</p>;
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`Staff and the job owner are notified. SpaceWorks never stops a machine because of a detection; that is your decision.`}</p>
    {select}
    {list.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(list.error)}</p> : <DetectionList rows={list.data?.results ?? []} />}
  </div>;
}

const RANGES = [{ hours: 1, label: () => t`Last hour` }, { hours: 24, label: () => t`Last 24 hours` }, { hours: 168, label: () => t`Last 7 days` }, { hours: 2160, label: () => t`Last 90 days` }];
export function chartOf(data: Telemetry): ChartData {
  const points = data.points.map(row => ({ x: Date.parse(row.ts), label: row.ts, value: Math.round(row.avg * 10) / 10 }));
  const name = data.selected;
  return { xKind: "time", xLabel: t`Time`, summary: t`${points.length} points for ${name}.`, series: points.length ? [{ id: name, label: name, unit: name.startsWith("temp.") ? "°C" : "", panelKey: name, points }] : [] };
}

/** Temperatures, power and sensor readings over time, thinned out as they age (raw 24 h, 1 minute 7 days, 15 minutes 90 days). */
export function AdapterTelemetry({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const { binding, select } = useBindingPick(makerspaceId, withCapability(adapter, "telemetry.history"));
  const [series, setSeries] = useState("");
  const [hours, setHours] = useState(24);
  const since = new Date(Math.floor(Date.now() / 60_000) * 60_000 - hours * 3_600_000).toISOString();
  const id = binding?.id ?? "";
  const names = useQuery({ queryKey: mediaKeys.telemetry(id, "", since), queryFn: () => mediaApi.telemetry(id, "", since), enabled: Boolean(binding) });
  const chosen = series || names.data?.series[0] || "";
  const shown = useQuery({ queryKey: mediaKeys.telemetry(id, chosen, since), queryFn: () => mediaApi.telemetry(id, chosen, since), enabled: Boolean(binding) && Boolean(chosen) });
  if (!binding) return <p className="text-sm text-muted">{t`No target on this adapter keeps a history.`}</p>;
  const current = shown.data;
  return <div className="grid gap-4">
    {select}
    <div className="flex flex-wrap gap-3">
      <Field label={t`Reading`}><select className="desk-input" value={chosen} onChange={event => setSeries(event.target.value)}>
        {names.data?.series.length ? names.data.series.map(name => <option key={name} value={name}>{name}</option>) : <option value="">{t`No readings yet`}</option>}</select></Field>
      <Field label={t`Period`}><select className="desk-input" value={hours} onChange={event => setHours(Number(event.target.value))}>
        {RANGES.map(range => <option key={range.hours} value={range.hours}>{range.label()}</option>)}</select></Field>
    </div>
    {names.isError || shown.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(names.error ?? shown.error)}</p>
      : current && chosen ? <MultiLineChart title={chosen} data={chartOf(current)} /> : <p className="text-sm text-muted">{t`Choose a reading to see its chart.`}</p>}
    {current ? <p className="text-xs text-muted">{current.resolution === 0 ? t`Showing every sample.` : current.resolution === 60 ? t`Showing one-minute averages.` : t`Showing fifteen-minute averages.`}</p> : null}
  </div>;
}
