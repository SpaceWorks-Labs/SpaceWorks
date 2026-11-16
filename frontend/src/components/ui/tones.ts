import type { Tone } from "./types";
/** Small status marks (pills, avatars, date chips, identity tiles): solid brand fills with ink labels in
 * both modes, the brand-tested pairs drawn on p.16 of the brand guidelines (docs/brand). */
export const toneMarkClasses: Record<Tone, string> = {
  success: "border-transparent bg-success text-on-success",
  warn: "border-transparent bg-warn text-on-warn",
  danger: "border-danger-line bg-panel text-danger",
  accent: "border-transparent bg-accent-soft text-accent-ink",
  info: "border-transparent bg-info text-on-info",
  emphasis: "border-emphasis bg-emphasis text-on-emphasis",
  neutral: "border-line bg-surface text-ink",
};
/** Large tinted areas (callouts, banners): solid in light, soft fill + tone ink in dark, so a
 * full-width block never glares on the Deep Ink ground. */
export const toneSurfaceClasses: Record<Tone, string> = {
  ...toneMarkClasses,
  success: `${toneMarkClasses.success} dark:bg-success-soft dark:text-success-ink`,
  warn: `${toneMarkClasses.warn} dark:bg-warn-soft dark:text-warn-ink`,
  info: `${toneMarkClasses.info} dark:bg-info-soft dark:text-info-ink`,
};
/** Compatibility name for existing importers: marks. */
export const toneClasses = toneMarkClasses;
const identityTones: Tone[] = ["accent", "info", "success", "warn"];
export function identityTone(seed: string): Tone {
  let hash = 0;
  for (const char of seed) hash = (Math.imul(hash, 31) + char.codePointAt(0)!) | 0;
  return identityTones[(hash >>> 0) % identityTones.length];
}
