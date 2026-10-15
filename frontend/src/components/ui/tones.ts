import type { Tone } from "./types";
export const toneClasses: Record<Tone, string> = {
  success: "border-transparent bg-success text-on-success dark:bg-success-soft dark:text-success-ink",
  warn: "border-transparent bg-warn text-on-warn dark:bg-warn-soft dark:text-warn-ink",
  danger: "border-danger-line bg-panel text-danger",
  accent: "border-transparent bg-accent-soft text-accent-ink",
  info: "border-transparent bg-info text-on-info dark:bg-info-soft dark:text-info-ink",
  emphasis: "border-emphasis bg-emphasis text-on-emphasis",
  neutral: "border-line bg-surface text-ink",
};
const identityTones: Tone[] = ["accent", "info", "success", "warn"];
export function identityTone(seed: string): Tone {
  let hash = 0;
  for (const char of seed) hash = (Math.imul(hash, 31) + char.codePointAt(0)!) | 0;
  return identityTones[(hash >>> 0) % identityTones.length];
}
