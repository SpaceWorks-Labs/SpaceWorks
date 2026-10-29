import type { Asset, PreviewKind } from "./types";

/** The server's registry decides which preview a file offers; the browser keeps no extension list. */
export const CANVAS = new Set<PreviewKind>(["mesh", "brep", "gerber", "kicad"]);

export function previewKind(asset: Asset | undefined): PreviewKind {
  return (asset?.preview as PreviewKind | undefined) ?? "download";
}

/** A KiCad file above the preview bound (below the upload cap) stays download-only. */
export function tooLarge(asset: Asset | undefined) {
  return previewKind(asset) === "kicad" && asset?.preview_max_bytes != null && (asset.bytes ?? 0) > asset.preview_max_bytes;
}
