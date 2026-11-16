import { t } from "@lingui/core/macro";
import { applyFilterOps, cssFilter, filterOps, placement, type CoverEdits } from "./coverMath";

export { DEFAULT_COVER_EDITS, type CoverEdits } from "./coverMath";

export const COVER_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_INPUT_BYTES = 10 * 1024 * 1024;

/** A friendly reason a picked file cannot be edited, or null when it is fine. */
export function coverFileProblem(file: { type: string; size: number }) {
  if (!file.size || file.size > MAX_INPUT_BYTES || !COVER_TYPES.includes(file.type)) return t`Choose a PNG, JPEG or WebP image up to 10 MiB.`;
  return null;
}

const supportsCanvasFilter = (context: CanvasRenderingContext2D) => typeof context.filter === "string";

/**
 * Render the edited cover at the shape's output size. The browser encodes WebP where it can (the server
 * re-encodes to WebP and strips metadata either way); a browser without a WebP encoder falls back to JPEG.
 */
export async function renderCover(source: Blob, edits: CoverEdits): Promise<Blob> {
  const problem = coverFileProblem(source);
  if (problem) throw new Error(problem);
  const bitmap = await createImageBitmap(source);
  try {
    if (bitmap.width * bitmap.height > 40_000_000) throw new Error(t`Choose an image smaller than 40 megapixels.`);
    const place = placement(edits, bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas"); canvas.width = place.W; canvas.height = place.H;
    const context = canvas.getContext("2d");
    if (!context) throw new Error(t`Your browser could not prepare the cover.`);
    const ops = filterOps(edits);
    const native = supportsCanvasFilter(context);
    if (native) context.filter = cssFilter(ops);
    context.translate(place.W / 2, place.H / 2);
    context.rotate(place.angle);
    context.translate(place.panX, place.panY);
    context.scale(place.flipX, place.flipY);
    const width = bitmap.width * place.scale, height = bitmap.height * place.scale;
    context.drawImage(bitmap, -width / 2, -height / 2, width, height);
    if (!native && ops.length && context.getImageData) {
      context.setTransform(1, 0, 0, 1, 0, 0);
      const pixels = context.getImageData(0, 0, place.W, place.H);
      applyFilterOps(pixels.data, ops);
      context.putImageData(pixels, 0, 0);
    }
    const encode = (type: string) => new Promise<Blob | null>(resolve => canvas.toBlob(resolve, type, 0.9));
    const webp = await encode("image/webp");
    const blob = webp?.type === "image/webp" ? webp : await encode("image/jpeg");
    if (!blob) throw new Error(t`Cover preparation failed.`);
    return blob;
  } finally { bitmap.close(); }
}

export const coverFileName = (blob: Blob) => blob.type === "image/webp" ? "event-cover.webp" : "event-cover.jpg";
