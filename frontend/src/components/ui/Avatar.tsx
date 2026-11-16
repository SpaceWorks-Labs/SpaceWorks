import { t } from "@lingui/core/macro";
import { identityTone, toneMarkClasses } from "./tones";
import type { Tone } from "./types";
export type AvatarProps = { name: string; seed?: string; tone?: Tone; size?: "sm" | "md" | "lg" };
export function Avatar({ name, seed = name, tone, size = "md" }: AvatarProps) {
  const initials = name.trim().split(/\s+/u).filter(Boolean).slice(0, 2).map(part => Array.from(part)[0]).join("").toLocaleUpperCase() || "?";
  const sizes = { sm: "h-8 w-8 text-xs", md: "h-11 w-11 text-sm", lg: "h-13 w-13 text-base" };
  return <span role="img" aria-label={name || t`Unknown person`}
    className={`inline-flex shrink-0 items-center justify-center rounded-full border font-semibold ${sizes[size]} ${toneMarkClasses[tone ?? identityTone(seed)]}`}>{initials}</span>;
}
