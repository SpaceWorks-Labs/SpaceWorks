// Sound and vibration at the desk: a short high beep for success, a low double beep for a refusal. Best
// effort only: a browser without audio or vibration just stays silent, and a collection never depends on it.
export function deskFeedback(ok: boolean) {
  try { navigator.vibrate?.(ok ? 60 : [80, 60, 80]); } catch { /* not supported */ }
  try {
    const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Context) return;
    const context = new Context();
    const beep = (at: number, hz: number) => {
      const osc = context.createOscillator(), gain = context.createGain();
      osc.frequency.value = hz; gain.gain.value = 0.08; osc.connect(gain); gain.connect(context.destination);
      osc.start(context.currentTime + at); osc.stop(context.currentTime + at + 0.12);
    };
    if (ok) beep(0, 880); else { beep(0, 220); beep(0.2, 220); }
    window.setTimeout(() => void context.close(), 700);
  } catch { /* not supported */ }
}
