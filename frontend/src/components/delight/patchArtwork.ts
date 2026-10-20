import { useSyncExternalStore } from "react";
import { currentTheme, subscribeTheme } from "../../lib/theme";
import type { DelightArtwork, DelightSource } from "./DelightProvider";

/**
 * Patch, the Space Works mascot, from SpaceWorks-Design `mascot/` (never recoloured,
 * mirrored or redrawn). Served from public/ and kept out of the kiosk precache
 * (scripts/kiosk-pwa.ts), because kiosk surfaces never show Patch.
 */
const base = "/brand/patch/";
// Every file has a dark twin from SpaceWorks-Design `mascot/dark/`: the same art with a thin Warm
// Cream sticker border, because Patch's dark outline measures only 1.0-2.3:1 on Deep Ink.
const pair = (name: string): ThemedFile => ({ light: `${base}${name}.webp`, dark: `${base}${name}-dark.webp` });
export type ThemedFile = { light: string; dark: string };
export const PATCH = {
  hero: pair("patch"),
  idle: pair("patch-idle"),
  sneeze: pair("patch-animated"),
  walk: pair("patch-walk-animated"),
  walkStill: pair("patch-walk-01"),
  nap: pair("patch-walk-06"),
  walkRight: pair("patch-walk-right"),
  walkLeft: pair("patch-walk-left"),
} as const;
/** Each walk sheet is eight 256x176 frames side by side; frame 6 (index 5) has the eyes closed. */
export const PATCH_WALK = { width: 256, height: 176, frames: 8, frameMs: 120, napFrame: 5 } as const;

/** The page theme (the `dark` class on <html>), so only the matching file is ever downloaded. */
export function usePageTheme(): keyof ThemedFile {
  return useSyncExternalStore(subscribeTheme, currentTheme, () => "light");
}

const art = (file: ThemedFile, extra: Partial<DelightSource> = {}): DelightSource => ({ ...file, patch: true, ...extra });

export const patchArtwork: DelightArtwork = {
  loader: art(PATCH.walk, { still: PATCH.walkStill }),
  welcome: art(PATCH.hero),
  // The sneeze vote: only for "the community acted together" (SuccessCard `celebrate`).
  success: art(PATCH.sneeze, { still: PATCH.idle }),
  waiting: art(PATCH.idle),
  empty: art(PATCH.idle),
  error: art(PATCH.idle),
  companionWalk: art(PATCH.walkRight, { frames: PATCH_WALK.frames }),
  companionFollow: art(PATCH.walkRight, { frames: PATCH_WALK.frames }),
  companionNap: art(PATCH.nap),
  companionPrint: art(PATCH.hero),
};
