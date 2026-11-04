import { readStorage, writeStorage } from "../../lib/safeStorage";

export const DOOR_SOUND_KEY = "spaceworks.door-sounds";
const soundEvent = "spaceworks-door-sounds";
export function doorSoundsEnabled() { return readStorage(DOOR_SOUND_KEY) === "on"; }
export function setDoorSounds(enabled: boolean) {
  writeStorage(DOOR_SOUND_KEY, enabled ? "on" : "off");
  window.dispatchEvent(new Event(soundEvent));
}
export function subscribeDoorSounds(change: () => void) {
  const storage = (event: StorageEvent) => { if (event.key === DOOR_SOUND_KEY || event.key === null) change(); };
  window.addEventListener(soundEvent, change);
  window.addEventListener("storage", storage);
  return () => { window.removeEventListener(soundEvent, change); window.removeEventListener("storage", storage); };
}

/** Invoke directly from a user gesture, after a committed result. Failures are harmless. */
export async function playDoorSound(kind: "success" | "already" | "blocked") {
  if (!doorSoundsEnabled() || navigator.userActivation?.isActive !== true) return;
  let context: AudioContext | undefined;
  try {
    context = new AudioContext();
    await context.resume();
    const start = context.currentTime;
    const notes = kind === "success" ? [523.25, 659.25] : [kind === "already" ? 220 : 164.81];
    notes.forEach((frequency, index) => {
      const oscillator = context!.createOscillator();
      const gain = context!.createGain();
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(.035, start + index * .13);
      gain.gain.exponentialRampToValueAtTime(.001, start + index * .13 + .12);
      oscillator.connect(gain); gain.connect(context!.destination);
      oscillator.start(start + index * .13); oscillator.stop(start + index * .13 + .13);
    });
    await new Promise(resolve => window.setTimeout(resolve, 350));
  } catch { /* Audio availability cannot change admission or handover. */ }
  finally { try { await context?.close(); } catch { /* Already closed. */ } }
}
