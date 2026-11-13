import { t } from "@lingui/core/macro";
import { useSyncExternalStore } from "react";
import { CheckCircle, CircleMinus, ShieldAlert } from "lucide-react";
import { useDelight, useReducedMotion } from "./DelightProvider";
import { doorSoundsEnabled, playDoorSound, setDoorSounds, subscribeDoorSounds } from "./doorSounds";
import { MoodGlyph } from "./Artwork";
import "./delight.css";

export function DoorSoundControl() {
  const on = useSyncExternalStore(subscribeDoorSounds, doorSoundsEnabled, () => false);
  const { enabled } = useDelight();
  if (!enabled) return null;
  return <button className="desk-button" type="button" aria-pressed={on} onClick={() => {
    setDoorSounds(!on);
  }}>{on ? t`Door sounds: on` : t`Door sounds: off`}</button>;
}

export function SuccessCard({ kind, name, message, resultId, accent = true }: {
  kind: "success" | "already" | "blocked"; name: string; message: string; resultId: string; accent?: boolean;
}) {
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  const soundOn = useSyncExternalStore(subscribeDoorSounds, doorSoundsEnabled, () => false);
  const Icon = kind === "success" ? CheckCircle : kind === "already" ? CircleMinus : ShieldAlert;
  return <section key={resultId} className={`grid gap-3 rounded-2xl border border-line bg-panel p-5 text-ink ${enabled && !reduced ? "sw-delight-result" : ""}`}>
    <div className="flex items-center gap-3"><Icon size={24} aria-hidden="true" className={kind === "success" ? "text-success-ink" : kind === "blocked" ? "text-danger" : "text-muted"} />
      <h2 className={accent ? "font-accent text-lg font-medium" : "title-section"}>{name}</h2><MoodGlyph mood={kind === "success" ? "success" : kind === "blocked" ? "error" : "waiting"} /></div>
    <p role="status">{message}</p>
    {enabled ? <div className="flex flex-wrap gap-3"><DoorSoundControl /><button type="button" className="desk-button" disabled={!soundOn}
      onClick={() => { void playDoorSound(kind); }}>{t`Play result sound`}</button></div> : null}
  </section>;
}
