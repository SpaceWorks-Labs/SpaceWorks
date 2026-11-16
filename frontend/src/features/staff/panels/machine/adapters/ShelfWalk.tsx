import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Binding, type IndicateMode, type TargetType } from "./adaptersApi";
import { useTargetOptions } from "./bindingTargets";
import { PointerTargetSelect } from "./PointerTargetSelect";
import { LogoLoader } from "../../../../../components/LogoLoader";

const SECONDS = 60;

/** "Walk the shelves": the pointer visits each storage location in turn so staff can check labels and bins by eye. */
export function ShelfWalk({ makerspaceId, binding }: { makerspaceId: number; binding: Binding }) {
  const { options, loading } = useTargetOptions(makerspaceId, "storage_location");
  const poses = useQuery({ queryKey: adapterKeys.poses(makerspaceId, binding.id), queryFn: () => adaptersApi.poses(binding.id) });
  const [index, setIndex] = useState<number | null>(null);
  const point = useMutation({ mutationFn: (value: { mode: IndicateMode; id: string }) =>
    adaptersApi.indicate(binding.id, { mode: value.mode, target_type: "storage_location", target_id: value.id, duration_seconds: SECONDS }) });
  const calibrated = new Set((poses.data ?? []).filter(row => row.target_type === "storage_location").map(row => row.target_id));
  const current = index === null ? null : options[index];
  const go = (next: number) => { const row = options[next]; if (!row) return; setIndex(next); if (calibrated.has(row.value)) point.mutate({ mode: "point", id: row.value }); else point.reset(); };
  const stop = () => { if (current && calibrated.has(current.value)) point.mutate({ mode: "clear", id: current.value }); setIndex(null); };
  if (loading) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  if (!options.length) return <p className="text-sm text-muted">{t`No storage locations yet. Give inventory items a storage location first.`}</p>;
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`The pointer visits each storage location for ${SECONDS} seconds. Locations without a saved position are skipped with a note.`}</p>
    {current ? <div className="grid gap-3 rounded-2xl border border-line bg-panel p-4" aria-live="polite">
      <p className="text-sm text-muted">{t`Location ${(index ?? 0) + 1} of ${options.length}`}</p>
      <p className="title-section break-words">{current.label}</p>
      {calibrated.has(current.value) ? <StatusPill label={t`Pointing now`} tone="success" /> : <StatusPill label={t`No saved position. Calibrate it first.`} tone="warn" />}
      {point.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(point.error)}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={(index ?? 0) === 0} onClick={() => go((index ?? 0) - 1)}>{t`Previous`}</button>
        <button type="button" className="desk-button-primary" disabled={(index ?? 0) >= options.length - 1} onClick={() => go((index ?? 0) + 1)}>{t`Next location`}</button>
        <button type="button" className="desk-button" onClick={stop}>{t`Stop`}</button>
      </div>
    </div> : <button type="button" className="desk-button-primary justify-self-start" onClick={() => go(0)}>{t`Walk the shelves`}</button>}
  </div>;
}

/** The one-off "Indicate" button: point at (or light up) a single storage location, item or box. */
export function ShelfIndicate({ makerspaceId, binding }: { makerspaceId: number; binding: Binding }) {
  const [type, setType] = useState<TargetType>("storage_location");
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<IndicateMode>("point");
  const [seconds, setSeconds] = useState(30);
  const [done, setDone] = useState("");
  const run = useMutation({ mutationFn: (next: IndicateMode) => adaptersApi.indicate(binding.id,
    { mode: next, target_type: type, target_id: target, ...(next === "clear" ? {} : { duration_seconds: seconds }) }),
  onSuccess: (_row, next) => setDone(next === "clear" ? t`Stopped.` : t`Sent. The pointer should be pointing now.`) });
  return <section className="grid gap-4 rounded-2xl border border-line bg-panel p-4" aria-label={t`Indicate`}>
    <h3 className="title-section">{t`Indicate`}</h3>
    <PointerTargetSelect makerspaceId={makerspaceId} type={type} onType={setType} value={target} onValue={setTarget} />
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`How`}><select className="desk-input" value={mode} onChange={event => setMode(event.target.value as IndicateMode)}>
        <option value="point">{t`Point at it`}</option><option value="light">{t`Light it up`}</option></select></Field>
      <Field label={t`For how long (seconds)`}><input className="desk-input" type="number" min={1} max={600} value={seconds} onChange={event => setSeconds(Math.min(600, Math.max(1, Number(event.target.value) || 1)))} /></Field>
    </div>
    {run.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(run.error)}</p> : null}
    {done && !run.isError ? <p role="status" className="text-sm text-muted">{done}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary" disabled={!target || run.isPending} onClick={() => { setDone(""); run.mutate(mode); }}>{t`Indicate`}</button>
      <button type="button" className="desk-button" disabled={!target || run.isPending} onClick={() => { setDone(""); run.mutate("clear"); }}>{t`Stop pointing`}</button>
    </div>
  </section>;
}
