import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, RelativeTime } from "../../../../../components/ui";
import { adapterErrorMessage, targetTypeLabel } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Binding, type Pose, type TargetType } from "./adaptersApi";
import { useTargetLabel } from "./bindingTargets";
import { PointerTargetSelect } from "./PointerTargetSelect";
import { BoxArt } from "../../../../../components/BoxSpinner";

const STEPS = [1, 5, 20];
type Axes = Record<string, string>;
const toPose = (axes: Axes): Pose["pose"] => Object.fromEntries(Object.entries(axes).filter(([, value]) => value.trim() !== "" && Number.isFinite(Number(value))).map(([key, value]) => [key, Number(value)]));

/** Calibration: jog or aim the pointer, save the pose it reports for a location, and keep the saved list tidy. */
export function ShelfCalibrate({ makerspaceId, binding }: { makerspaceId: number; binding: Binding }) {
  const client = useQueryClient();
  const [step, setStep] = useState(5);
  const [axes, setAxes] = useState<Axes>({ pan: "", tilt: "" });
  const [type, setType] = useState<TargetType>("storage_location");
  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const [clearing, setClearing] = useState<Pose | null>(null);
  const position = useQuery({ queryKey: adapterKeys.position(makerspaceId, binding.id), queryFn: () => adaptersApi.position(binding.id), refetchInterval: 3_000 });
  const poses = useQuery({ queryKey: adapterKeys.poses(makerspaceId, binding.id), queryFn: () => adaptersApi.poses(binding.id) });
  const label = useTargetLabel(makerspaceId, [{ target_type: "storage_location" }, { target_type: "item" }, { target_type: "box" }] as Binding[]);
  const reported = position.data?.pose;
  useEffect(() => {
    if (reported) setAxes(Object.fromEntries(Object.entries(reported).map(([key, value]) => [key, String(value)])));
  }, [reported]);
  const refresh = () => { void client.invalidateQueries({ queryKey: adapterKeys.poses(makerspaceId, binding.id) }); };
  const jog = useMutation({ mutationFn: (move: { dx?: number; dy?: number }) => adaptersApi.jog(binding.id, move) });
  const aim = useMutation({ mutationFn: (pose: Pose["pose"]) => adaptersApi.aim(binding.id, pose) });
  const save = useMutation({ mutationFn: () => adaptersApi.savePose(binding.id, { target_type: type, target_id: target, pose: toPose(axes), ...(note.trim() ? { note: note.trim() } : {}) }),
    onSuccess: () => { setNote(""); refresh(); } });
  const clear = useMutation({ mutationFn: (row: Pose) => adaptersApi.clearPose(binding.id, { target_type: row.target_type, target_id: row.target_id }),
    onSuccess: () => { setClearing(null); refresh(); } });
  const pose = toPose(axes);
  const error = jog.error ?? aim.error ?? save.error ?? clear.error;
  const arrow = (text: string, name: string, move: { dx?: number; dy?: number }) =>
    <button type="button" className="desk-button min-h-11 min-w-11" aria-label={name} disabled={jog.isPending} onClick={() => jog.mutate(move)}>{text}</button>;
  return <div className="grid gap-6">
    <section className="grid gap-4 rounded-2xl border border-line bg-panel p-4" aria-label={t`Aim the pointer`}>
      <h3 className="title-section">{t`Aim the pointer`}</h3>
      <div className="flex flex-wrap items-center gap-6">
        <div className="grid grid-cols-3 gap-1" role="group" aria-label={t`Jog`}>
          <span />{arrow("▲", t`Jog up`, { dy: step })}<span />
          {arrow("◀", t`Jog left`, { dx: -step })}<span aria-hidden="true" className="grid place-items-center text-muted">●</span>{arrow("▶", t`Jog right`, { dx: step })}
          <span />{arrow("▼", t`Jog down`, { dy: -step })}<span />
        </div>
        <Field label={t`Step size`}><select className="desk-input" value={step} onChange={event => setStep(Number(event.target.value))}>
          {STEPS.map(size => <option key={size} value={size}>{size}</option>)}</select></Field>
      </div>
      <p className="text-sm text-muted" role="status">{reported ? t`Reported position:` : t`The pointer has not reported a position in the last five minutes.`}
        {reported ? ` ${Object.entries(reported).map(([key, value]) => `${key} ${value}`).join(", ")}` : ""}</p>
      <div className="flex flex-wrap items-end gap-3">
        {Object.keys(axes).map(key => <Field key={key} label={key} className="w-32 min-w-0"><input className="desk-input w-full min-w-0" inputMode="decimal" value={axes[key]}
          onChange={event => setAxes({ ...axes, [key]: event.target.value })} /></Field>)}
        <button type="button" className="desk-button" disabled={!Object.keys(pose).length || aim.isPending} onClick={() => aim.mutate(pose)}>{t`Aim here`}</button>
      </div>
    </section>
    <section className="grid gap-4 rounded-2xl border border-line bg-panel p-4" aria-label={t`Save this position`}>
      <h3 className="title-section">{t`Save this position`}</h3>
      <PointerTargetSelect makerspaceId={makerspaceId} type={type} onType={setType} value={target} onValue={setTarget} />
      <Field label={t`Note (optional)`}><input className="desk-input" maxLength={80} value={note} onChange={event => setNote(event.target.value)} /></Field>
      <button type="button" className="desk-button-primary justify-self-start" disabled={!target || !Object.keys(pose).length || save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save position`}</button>
    </section>
    {error ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(error)}</p> : null}
    <section className="grid gap-3" aria-label={t`Saved positions`}>
      <h3 className="title-section">{t`Saved positions`}</h3>
      {poses.data?.length ? <ul className="grid gap-2">{poses.data.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-3">
        <div className="min-w-0 flex-1"><p className="font-semibold break-words">{label(row.target_type as TargetType, null, row.target_id)}</p>
          <p className="text-sm text-muted">{targetTypeLabel(row.target_type)} · {Object.entries(row.pose).map(([key, value]) => `${key} ${value}`).join(", ")}
            {row.note ? ` · ${row.note}` : ""} · <RelativeTime date={row.updated_at} /></p></div>
        <button type="button" className="desk-button" onClick={() => { setType(row.target_type as TargetType); setTarget(row.target_id);
          setAxes(Object.fromEntries(Object.entries(row.pose).map(([key, value]) => [key, String(value)]))); aim.mutate(row.pose); }}>{t`Re-calibrate`}</button>
        {clearing?.id === row.id ? <span className="flex gap-2"><button type="button" className="desk-button" onClick={() => setClearing(null)}>{t`Keep`}</button>
          <button type="button" className="desk-button-danger" disabled={clear.isPending} onClick={() => clear.mutate(row)}>{t`Clear position`}</button></span>
          : <button type="button" className="desk-button" aria-label={t`Clear ${label(row.target_type as TargetType, null, row.target_id)}`} onClick={() => setClearing(row)}>{t`Clear`}</button>}
      </li>)}</ul> : <p className="text-sm text-muted">{poses.isLoading ? t`Loading…` : t`No positions saved yet. Aim the pointer at a shelf, then save it.`}</p>}
    </section>
  </div>;
}
