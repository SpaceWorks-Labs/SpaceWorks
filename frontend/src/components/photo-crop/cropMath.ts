// Crop maths for card photos (SPEC §6: crop to the design's photo frame, in the browser).
// Everything is in source-image pixels: a frame of the given aspect (width / height), zoomed
// in from the largest frame that fits, centred on (cx, cy) and always kept inside the image.

export type CropView = { zoom: number; cx: number; cy: number };
export type CropRect = { sx: number; sy: number; sw: number; sh: number };

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;
export const OUTPUT_LONG_EDGE = 1200;

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

/** The largest frame of this aspect that fits inside the image. */
export function baseFrame(width: number, height: number, aspect: number) {
  const safe = aspect > 0 && Number.isFinite(aspect) ? aspect : 1;
  const frameWidth = Math.min(width, height * safe);
  return { width: frameWidth, height: frameWidth / safe };
}

export function initialView(width: number, height: number): CropView {
  return { zoom: MIN_ZOOM, cx: width / 2, cy: height / 2 };
}

/** Keep the zoom in range and the frame inside the image. */
export function clampView(view: CropView, width: number, height: number, aspect: number): CropView {
  const zoom = clamp(view.zoom, MIN_ZOOM, MAX_ZOOM);
  const frame = baseFrame(width, height, aspect);
  const halfW = frame.width / zoom / 2, halfH = frame.height / zoom / 2;
  return { zoom, cx: clamp(view.cx, halfW, width - halfW), cy: clamp(view.cy, halfH, height - halfH) };
}

export function cropRect(view: CropView, width: number, height: number, aspect: number): CropRect {
  const safe = clampView(view, width, height, aspect);
  const frame = baseFrame(width, height, aspect);
  const sw = frame.width / safe.zoom, sh = frame.height / safe.zoom;
  return { sx: safe.cx - sw / 2, sy: safe.cy - sh / 2, sw, sh };
}

/** Drag the picture by (dx, dy) screen pixels on a preview `previewWidth` wide: the frame moves the other way. */
export function pan(view: CropView, dx: number, dy: number, previewWidth: number, width: number, height: number,
  aspect: number): CropView {
  const rect = cropRect(view, width, height, aspect);
  const scale = rect.sw / Math.max(1, previewWidth);
  return clampView({ ...view, cx: view.cx - dx * scale, cy: view.cy - dy * scale }, width, height, aspect);
}

export function zoomTo(view: CropView, zoom: number, width: number, height: number, aspect: number): CropView {
  return clampView({ ...view, zoom }, width, height, aspect);
}

/** Output size: the crop's own pixels, but never more than OUTPUT_LONG_EDGE on the long side. */
export function outputSize(rect: CropRect) {
  const scale = Math.min(1, OUTPUT_LONG_EDGE / Math.max(rect.sw, rect.sh));
  return { width: Math.max(1, Math.round(rect.sw * scale)), height: Math.max(1, Math.round(rect.sh * scale)) };
}
