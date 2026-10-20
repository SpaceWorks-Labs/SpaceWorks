import type { DelightArtwork, DelightSource } from "./DelightProvider";

/**
 * Patch, the Space Works mascot, from SpaceWorks-Design `mascot/` (never recoloured,
 * mirrored or redrawn). Served from public/ and kept out of the kiosk precache
 * (scripts/kiosk-pwa.ts), because kiosk surfaces never show Patch.
 */
const base = "/brand/patch/";
export const PATCH = {
  hero: `${base}patch.webp`,
  idle: `${base}patch-idle.webp`,
  sneeze: `${base}patch-animated.webp`,
  walk: `${base}patch-walk-animated.webp`,
  walkStill: `${base}patch-walk-01.webp`,
  nap: `${base}patch-walk-06.webp`,
  walkRight: `${base}patch-walk-right.webp`,
  walkLeft: `${base}patch-walk-left.webp`,
} as const;
/** Each walk sheet is eight 256x176 frames side by side; frame 6 (index 5) has the eyes closed. */
export const PATCH_WALK = { width: 256, height: 176, frames: 8, frameMs: 120, napFrame: 5 } as const;

// Patch is never recoloured, so light and dark share one file; dark mode adds a light plate.
const art = (src: string, extra: Partial<DelightSource> = {}): DelightSource => ({ light: src, dark: src, patch: true, ...extra });

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
