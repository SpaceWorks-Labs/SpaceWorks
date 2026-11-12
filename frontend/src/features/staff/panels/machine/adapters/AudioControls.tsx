import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { useMutation } from "@tanstack/react-query";

import { Callout } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import type { WatchAudio } from "./adaptersApi";
import { AUDIO_RECORDING_DAYS, mediaApi } from "./adaptersMediaApi";

/** What the viewer may choose when opening a watch (decision 321a). Listening is off unless chosen; talk implies listening. */
export function AudioOptions({ canListen, canTalk, canRecord, record, value, onChange }: {
  canListen: boolean; canTalk: boolean; canRecord: boolean; record: boolean; value: WatchAudio; onChange: (next: WatchAudio) => void;
}) {
  if (!canListen) return null;
  const audible = value.listen || value.talk;
  return <fieldset className="grid gap-2 rounded-xl border border-line p-3">
    <legend className="px-1 text-sm font-semibold">{t`Sound`}</legend>
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={Boolean(value.listen || value.talk)} disabled={Boolean(value.talk)}
      onChange={event => onChange({ ...value, listen: event.target.checked })} />
      <span><strong>{t`Listen to the device`}</strong><span className="block text-muted">{t`Receive only. You hear the device; it does not hear you.`}</span></span></label>
    {canTalk ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={Boolean(value.talk)}
      onChange={event => onChange({ ...value, listen: event.target.checked || value.listen, talk: event.target.checked })} />
      <span><strong>{t`Allow push-to-talk`}</strong><span className="block text-muted">{t`You speak only while you hold the talk button. Every press is in the audit log.`}</span></span></label> : null}
    {audible ? <Callout size="inline" tone="warn" lead={t`People near the device may hear this.`}
      body={t`The device announces on site that audio is open, for example with a chime or a light. Do not use it to listen in on people who do not know.`} /> : null}
    {audible && record && canRecord ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={Boolean(value.noticeAck)}
      onChange={event => onChange({ ...value, noticeAck: event.target.checked })} />
      <span><strong>{t`I confirm the audio notice is displayed at the device`}</strong>
        <span className="block text-muted">{t`Required to record sound. Audio recordings are private to staff and deleted after ${AUDIO_RECORDING_DAYS} days.`}</span></span></label> : null}
  </fieldset>;
}

/** Mute and, where allowed, push-to-talk while a watch is open. The microphone is enabled only while the button is held. */
export function AudioLive({ watchId, talk, muted, onMute, mic }: { watchId: string; talk: boolean; muted: boolean; onMute: (next: boolean) => void; mic: MutableRefObject<MediaStreamTrack | null> }) {
  const [holding, setHolding] = useState(false);
  const held = useRef(false);
  const press = useMutation({ mutationFn: (active: boolean) => mediaApi.talk(watchId, active) });
  const set = (active: boolean) => {
    if (held.current === active) return;
    held.current = active; setHolding(active);
    if (mic.current) mic.current.enabled = active;
    press.mutate(active);
  };
  useEffect(() => () => { if (held.current && mic.current) mic.current.enabled = false; }, [mic]);
  return <div className="grid gap-2" aria-label={t`Sound controls`}>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button" aria-pressed={muted} onClick={() => onMute(!muted)}>{muted ? t`Unmute` : t`Mute`}</button>
      {talk ? <button type="button" className={holding ? "desk-button-danger" : "desk-button-primary"} aria-pressed={holding}
        onPointerDown={() => set(true)} onPointerUp={() => set(false)} onPointerLeave={() => set(false)} onPointerCancel={() => set(false)}
        onKeyDown={event => { if ((event.key === " " || event.key === "Enter") && !event.repeat) { event.preventDefault(); set(true); } }}
        onKeyUp={event => { if (event.key === " " || event.key === "Enter") set(false); }}>{holding ? t`Talking… release to stop` : t`Hold to talk`}</button> : null}
    </div>
    {talk && holding ? <p role="status" className="text-sm font-semibold text-danger">{t`The device can hear you now.`}</p> : null}
    {press.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(press.error)}</p> : null}
  </div>;
}
