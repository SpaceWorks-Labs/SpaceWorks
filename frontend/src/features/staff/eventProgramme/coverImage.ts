import { t } from "@lingui/core/macro";
export type CoverEdits = { ratio: "16:7" | "16:9" | "1:1"; rotation: number; straighten: number; brightness: number; contrast: number; x: number; y: number; zoom: number };
export const DEFAULT_COVER_EDITS: CoverEdits = { ratio: "16:7", rotation: 0, straighten: 0, brightness: 100, contrast: 100, x: 50, y: 50, zoom: 1 };
export async function renderCover(source: Blob, edits: CoverEdits): Promise<Blob> {
  if (!source.size || source.size > 10 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(source.type)) throw new Error(t`Choose a PNG, JPEG or WebP image up to 10 MiB.`);
  const bitmap = await createImageBitmap(source);
  try {
    if (bitmap.width * bitmap.height > 40_000_000) throw new Error(t`Choose an image smaller than 40 megapixels.`);
    const [a, b] = edits.ratio.split(":").map(Number);
    const canvas = document.createElement("canvas"); canvas.width = 1600; canvas.height = Math.round(1600 * b / a);
    const context = canvas.getContext("2d");
    if (!context) throw new Error(t`Your browser could not prepare the cover.`);
    context.fillStyle = "#FFF4E8"; context.fillRect(0, 0, canvas.width, canvas.height);
    context.translate(canvas.width / 2, canvas.height / 2);
    const angle = (edits.rotation + edits.straighten) * Math.PI / 180;
    context.rotate(angle);
    const requiredWidth = Math.abs(Math.cos(angle)) * canvas.width + Math.abs(Math.sin(angle)) * canvas.height;
    const requiredHeight = Math.abs(Math.sin(angle)) * canvas.width + Math.abs(Math.cos(angle)) * canvas.height;
    const scale = Math.max(requiredWidth / bitmap.width, requiredHeight / bitmap.height) * edits.zoom;
    context.filter = `brightness(${edits.brightness}%) contrast(${edits.contrast}%)`;
    const width = bitmap.width * scale; const height = bitmap.height * scale;
    context.drawImage(bitmap, -width / 2 + (edits.x - 50) / 100 * Math.max(0, width - requiredWidth), -height / 2 + (edits.y - 50) / 100 * Math.max(0, height - requiredHeight), width, height);
    return await new Promise<Blob>((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error(t`Cover preparation failed.`)), "image/jpeg", 0.9));
  } finally { bitmap.close(); }
}
