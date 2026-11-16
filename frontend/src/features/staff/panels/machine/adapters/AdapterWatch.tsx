import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Callout, Field } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { AudioLive, AudioOptions } from "./AudioControls";
import { adaptersApi, RECORDING_DAYS, type AdapterSummary, type AdapterSwitches, type Watch, type WatchAudio } from "./adaptersApi";
import { useTargetLabel } from "./bindingTargets";
import { WatchViewer, type WatchTransport } from "./WatchViewer";
import { BoxArt } from "../../../../../components/BoxSpinner";

const isCamera = (caps: string[]) => caps.includes("media.snapshot") || caps.includes("media.stream");

/** A camera watch (child switch `machines.integrations.video`): five minutes, one audit row naming the viewer, the camera sends only while it is open. */
export function AdapterWatch({ makerspaceId, adapter, recordingEnabled, switches }: { makerspaceId: number; adapter: AdapterSummary; recordingEnabled: boolean; switches?: AdapterSwitches }) {
  const cameras = adapter.bindings.filter(row => isCamera(row.capabilities));
  const label = useTargetLabel(makerspaceId, cameras);
  const [bindingId, setBindingId] = useState(cameras[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [record, setRecord] = useState(false);
  const [audio, setAudio] = useState<WatchAudio>({});
  const [muted, setMuted] = useState(false);
  const mic = useRef<MediaStreamTrack | null>(null);
  const [watch, setWatch] = useState<Watch | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [asked, setAsked] = useState("");
  useEffect(() => { if (!watch || watch.ended_at) return; const timer = window.setInterval(() => setNow(Date.now()), 1_000); return () => window.clearInterval(timer); }, [watch]);
  const start = useMutation({ mutationFn: () => adaptersApi.startWatch((bindingId || cameras[0]?.id) as string, reason.trim(), recordingEnabled && record, audio), onSuccess: row => { setWatch(row); setAsked(""); } });
  const still = useMutation({ mutationFn: () => adaptersApi.snapshot(watch!.id), onSuccess: () => setAsked(t`A fresh still was requested from the camera.`) });
  const stop = useMutation({ mutationFn: () => adaptersApi.endWatch(watch!.id), onSuccess: row => { setWatch(row.ended_at ? row : { ...watch!, ended_at: new Date().toISOString() }); } });
  if (!cameras.length) return <p className="text-sm text-muted">{t`No camera is bound to this adapter.`}</p>;
  const remaining = watch && !watch.ended_at ? Math.max(0, Math.floor((new Date(watch.expires_at).getTime() - now) / 1_000)) : 0;
  const camera = cameras.find(row => row.id === (bindingId || cameras[0]?.id));
  const open = Boolean(watch && !watch.ended_at && remaining > 0);
  const error = start.error ?? still.error ?? stop.error;
  const transport: WatchTransport | null = watch ? { poll: after => adaptersApi.poll(watch.id, after), signal: body => adaptersApi.signal(watch.id, body), frame: () => adaptersApi.frame(watch.id) } : null;
  return <div className="grid gap-4">
    <Callout size="inline" tone="warn" lead={t`Only while watching.`}
      body={t`The camera sends nothing until you start a watch. A watch lasts five minutes, and starting one is recorded in the audit log with your name.`} />
    {cameras.length > 1 ? <Field label={t`Camera`}><select className="desk-input" value={bindingId} disabled={open} onChange={event => setBindingId(event.target.value)}>
      {cameras.map(row => <option key={row.id} value={row.id}>{label(row.target_type, row.machine_id, row.target_id, row.external_ref)}</option>)}</select></Field> : null}
    {open && transport ? <div className="grid gap-3 rounded-2xl border border-line bg-panel p-4" aria-live="polite">
      <p className="title-section">{t`Watching`}</p>
      <p className="text-sm text-muted">{t`Closes in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`}{watch?.record ? ` · ${t`Recording`}` : ""}</p>
      <WatchViewer transport={transport} label={t`Camera view`} audio={watch?.talk ? "talk" : watch?.audio ? "listen" : "off"} muted={muted} mic={mic} />
      {watch?.audio ? <AudioLive watchId={watch.id} talk={Boolean(watch.talk)} muted={muted} onMute={setMuted} mic={mic} /> : null}
      {watch?.record ? <Callout size="inline" tone="danger" lead={t`This watch is being recorded.`} body={t`The recording is private to staff and deleted ${RECORDING_DAYS} days after the watch. Starting it is in the audit log.`} /> : null}
      {asked ? <p role="status" className="text-sm text-muted">{asked}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={still.isPending} onClick={() => still.mutate()}>{t`Request a fresh still`}</button>
        <button type="button" className="desk-button-danger" disabled={stop.isPending} onClick={() => stop.mutate()}>{t`Stop watching`}</button></div>
    </div> : <form className="grid gap-3 rounded-2xl border border-line bg-panel p-4" onSubmit={event => { event.preventDefault(); start.mutate(); }}>
      <Field label={t`Why are you watching? (optional)`} hint={t`Kept with the audit entry.`}><input className="desk-input" maxLength={120} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <AudioOptions canListen={Boolean(switches?.audio && camera?.capabilities.includes("media.audio") && camera.capabilities.includes("media.stream"))} canTalk={Boolean(switches?.talk && camera?.capabilities.includes("media.talk"))}
        canRecord={Boolean(switches?.audioRecording)} record={recordingEnabled && record} value={audio} onChange={setAudio} />
      {recordingEnabled ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={record} onChange={event => setRecord(event.target.checked)} />
        <span><strong>{t`Also record this watch`}</strong><span className="block text-muted">{t`Off by default. A recording is private to staff, kept for ${RECORDING_DAYS} days, then deleted. Anyone in the frame is recorded, so tell them.`}</span></span></label> : null}
      {watch?.ended_at ? <p role="status" className="text-sm text-muted">{t`The last watch has ended.`}</p> : null}
      <button type="submit" className="desk-button-primary justify-self-start" disabled={start.isPending}>{start.isPending ? <><BoxArt size={16} mono />{t`Starting…`}</> : record && recordingEnabled ? t`Start watching and recording` : t`Start watching`}</button>
    </form>}
    {error ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(error)}</p> : null}
  </div>;
}
