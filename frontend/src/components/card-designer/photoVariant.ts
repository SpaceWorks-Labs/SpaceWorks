// Which picture a photo layer shows: the TS twin of the server's `rendering_photo.photo_source` (CARD-STUDIO-SPEC
// section 7). `cutout` prints the cut-out when one is ready, `auto` only when the holder (or staff) chose "Use cut-out",
// and anything missing falls back to the original photo, so a card is never blank.
import type { Layer } from "./cardTypes";

/** What the preview knows about the person on the card. Sample people get the procedural silhouette as their cut-out
 *  (the server's `studio_samples.silhouette_png`, with use-cut-out on). */
export type PhotoState = { cutout: string | null; useCutout: boolean; sample: boolean };

export const SAMPLE_PHOTO: PhotoState = { cutout: null, useCutout: true, sample: true };

export type PhotoPick = "cutout" | "silhouette" | "original";

export function pickPhoto(variant: Layer["variant"], state: PhotoState): PhotoPick {
  const wanted = variant === "cutout" || (variant === "auto" && state.useCutout);
  if (!wanted) return "original";
  if (state.cutout) return "cutout";
  return state.sample ? "silhouette" : "original";
}

/** The preview state for a real holder: the cut-out link when one is ready, and their own choice. */
export function holderPhotoState(cutoutUrl: string | null, holderCutout?: { available: boolean; use_cutout: boolean }): PhotoState {
  return { cutout: holderCutout?.available ? cutoutUrl : null, useCutout: Boolean(holderCutout?.use_cutout), sample: false };
}
