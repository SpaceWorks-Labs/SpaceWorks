// Canvas maths kept out of the component so it can be tested: zoom sizing, pointer deltas in
// millimetres, snapping a moved box (grid, guides, equal spacing) and proportional resizing.
import type { Layer, Side } from "./cardTypes";
import { clamp, qrMinimum, round1, SAFE_AREA_MM, snap } from "./cardGeometry";
import { BARCODE_MIN_HEIGHT_MM, BARCODE_MIN_WIDTH_MM } from "./designDocument";
import { boundsOf, type Box, type Patches } from "./selection";

export type Zoom = "fit" | 1 | 1.5 | 2;
export const ZOOMS: { value: Zoom; label: string }[] = [
  { value: "fit", label: "Fit" }, { value: 1, label: "100 %" }, { value: 1.5, label: "150 %" }, { value: 2, label: "200 %" },
];
export const SNAP_THRESHOLD_MM = 1.2;

export type Guide = { axis: "x" | "y"; at: number };
/** An equal-spacing hint: two gaps of the same size along one axis, drawn at `cross`. */
export type SpacingHint = { axis: "x" | "y"; gaps: [number, number][]; cross: number };

/** Width of the drawn card. 100 % fills the column; Fit also keeps a tall card within `maxHeight`. */
export function canvasWidth(containerWidth: number, maxHeight: number, pageWidth: number, pageHeight: number, zoom: Zoom) {
  if (zoom === "fit") return Math.max(120, Math.min(containerWidth, maxHeight * pageWidth / pageHeight));
  return Math.max(120, containerWidth * zoom);
}

/** The largest width that fits a page inside a box (thumbnails). */
export function fitInside(boxWidth: number, boxHeight: number, pageWidth: number, pageHeight: number) {
  return Math.min(boxWidth, boxHeight * pageWidth / pageHeight);
}

/** Pointer movement in millimetres; `px` is CSS pixels per millimetre at the current zoom. */
export function pointerDeltaMm(start: { x: number; y: number }, now: { x: number; y: number }, px: number) {
  return { dx: (now.x - start.x) / px, dy: (now.y - start.y) / px };
}

/** A pointer position on the card in millimetres, from the card's on-screen rectangle. */
export function pointerToMm(clientX: number, clientY: number, rect: { left: number; top: number }, px: number) {
  return { x: (clientX - rect.left) / px, y: (clientY - rect.top) / px };
}

function guideLines(side: Side, exclude: Set<string>) {
  const xs = [0, side.page_width_mm / 2, side.page_width_mm, SAFE_AREA_MM, side.page_width_mm - SAFE_AREA_MM];
  const ys = [0, side.page_height_mm / 2, side.page_height_mm, SAFE_AREA_MM, side.page_height_mm - SAFE_AREA_MM];
  for (const other of side.layers) {
    if (exclude.has(other.id) || other.hidden) continue;
    xs.push(other.x_mm, other.x_mm + other.w_mm / 2, other.x_mm + other.w_mm);
    ys.push(other.y_mm, other.y_mm + other.h_mm / 2, other.y_mm + other.h_mm);
  }
  return { xs, ys };
}

/** Snap a box's edges or centre to the card, the safe area and the other layers. */
export function snapBox(side: Side, exclude: Set<string>, box: Box, threshold = SNAP_THRESHOLD_MM) {
  const { xs, ys } = guideLines(side, exclude);
  const guides: Guide[] = [];
  const pick = (start: number, size: number, lines: number[], axis: "x" | "y") => {
    for (const offset of [0, size / 2, size]) {
      const hit = lines.find((line) => Math.abs(start + offset - line) <= threshold);
      if (hit !== undefined) { guides.push({ axis, at: hit }); return round1(hit - offset); }
    }
    return null;
  };
  return { x: pick(box.x, box.w, xs, "x"), y: pick(box.y, box.h, ys, "y"), guides };
}

/** Centre a box between its nearest neighbours when the two gaps nearly match. */
export function equalSpacing(side: Side, exclude: Set<string>, box: Box, threshold = SNAP_THRESHOLD_MM) {
  const others = side.layers.filter((layer) => !exclude.has(layer.id) && !layer.hidden);
  const along = (axis: "x" | "y") => {
    const [pos, size, cpos, csize] = axis === "x" ? ["x_mm", "w_mm", "y_mm", "h_mm"] as const : ["y_mm", "h_mm", "x_mm", "w_mm"] as const;
    const start = axis === "x" ? box.x : box.y, length = axis === "x" ? box.w : box.h;
    const cross = axis === "x" ? box.y : box.x, crossLength = axis === "x" ? box.h : box.w;
    const lane = others.filter((layer) => layer[cpos] < cross + crossLength && layer[cpos] + layer[csize] > cross);
    const before = lane.filter((layer) => layer[pos] + layer[size] <= start + threshold)
      .sort((a, b) => b[pos] + b[size] - (a[pos] + a[size]))[0];
    const after = lane.filter((layer) => layer[pos] >= start + length - threshold).sort((a, b) => a[pos] - b[pos])[0];
    if (!before || !after) return null;
    const left = before[pos] + before[size], right = after[pos];
    const gap = (right - left - length) / 2;
    if (gap <= 0 || Math.abs(start - (left + gap)) > threshold) return null;
    const at = round1(left + gap);
    return { at, hint: { axis, cross: cross + crossLength / 2, gaps: [[left, at], [at + length, right]] } as SpacingHint };
  };
  const x = along("x"), y = along("y");
  return { x: x?.at ?? null, y: y?.at ?? null, hints: [x?.hint, y?.hint].filter((hint): hint is SpacingHint => Boolean(hint)) };
}

/** Move a selection from where the drag started: grid, then guides, then equal spacing (unless
 *  `free`, Alt held), clamped so the selection stays on the card. */
export function moveSelection(side: Side, start: Layer[], dx: number, dy: number, options: { gridMm: number; free?: boolean }) {
  const box = boundsOf(start);
  if (!box) return { patches: {} as Patches, guides: [] as Guide[], hints: [] as SpacingHint[], box: null };
  const exclude = new Set(start.map((layer) => layer.id));
  let x = box.x + dx, y = box.y + dy;
  let guides: Guide[] = [], hints: SpacingHint[] = [];
  if (!options.free) {
    x = snap(x, options.gridMm); y = snap(y, options.gridMm);
    const snapped = snapBox(side, exclude, { ...box, x, y });
    const spaced = equalSpacing(side, exclude, { ...box, x, y });
    guides = snapped.guides;
    if (snapped.x !== null) x = snapped.x; else if (spaced.x !== null) x = spaced.x;
    if (snapped.y !== null) y = snapped.y; else if (spaced.y !== null) y = spaced.y;
    hints = spaced.hints.filter((hint) => (hint.axis === "x" ? snapped.x === null : snapped.y === null));
  }
  x = clamp(x, 0, Math.max(0, side.page_width_mm - box.w));
  y = clamp(y, 0, Math.max(0, side.page_height_mm - box.h));
  const shiftX = x - box.x, shiftY = y - box.y;
  const patches: Patches = {};
  for (const layer of start) patches[layer.id] = { x_mm: round1(layer.x_mm + shiftX), y_mm: round1(layer.y_mm + shiftY) };
  return { patches, guides, hints, box: { ...box, x: round1(x), y: round1(y) } };
}

const PROPORTIONAL = new Set(["photo", "image", "logo"]);

export function minimumSize(layer: Layer, stock: string, side: Side) {
  if (layer.kind === "desk_qr" || layer.kind === "verify_qr") return { w: qrMinimum(stock), h: qrMinimum(stock) };
  if (layer.kind === "barcode") {
    const width = BARCODE_MIN_WIDTH_MM[layer.source === "desk" ? "desk" : "number"];
    return { w: Math.min(width, side.page_width_mm - layer.x_mm), h: BARCODE_MIN_HEIGHT_MM };
  }
  return { w: 1, h: 0.5 };
}

/** Resize from the bottom-right handle. Photos, images and logos keep their shape unless Shift
 *  is held; other layers keep it only with Shift; QR codes are always square. */
export function resizeLayer(side: Side, layer: Layer, dx: number, dy: number,
  options: { gridMm: number; stock: string; shift?: boolean; free?: boolean }) {
  const min = minimumSize(layer, options.stock, side);
  const maxW = side.page_width_mm - layer.x_mm, maxH = side.page_height_mm - layer.y_mm;
  const step = (value: number) => (options.free ? round1(value) : snap(value, options.gridMm / 2));
  const qr = layer.kind === "desk_qr" || layer.kind === "verify_qr";
  const keepRatio = qr || (PROPORTIONAL.has(layer.kind) ? !options.shift : Boolean(options.shift));
  if (!keepRatio) {
    return { w_mm: clamp(step(layer.w_mm + dx), min.w, Math.max(min.w, maxW)),
      h_mm: clamp(step(layer.h_mm + dy), min.h, Math.max(min.h, maxH)) };
  }
  const ratio = qr ? 1 : layer.w_mm / (layer.h_mm || 1);
  const scale = Math.max((layer.w_mm + dx) / layer.w_mm, (layer.h_mm + dy) / layer.h_mm);
  let w = step(layer.w_mm * scale);
  w = clamp(w, Math.max(min.w, min.h * ratio), Math.max(min.w, Math.min(maxW, maxH * ratio)));
  return { w_mm: round1(w), h_mm: round1(w / ratio) };
}

/** The angle for the rotate handle: QR and barcodes snap to right angles, Shift snaps to 15°. */
export function rotationAt(layer: Layer, centre: { x: number; y: number }, pointer: { x: number; y: number }, shift: boolean) {
  let angle = Math.atan2(pointer.y - centre.y, pointer.x - centre.x) * 180 / Math.PI + 90;
  const square = layer.kind === "desk_qr" || layer.kind === "verify_qr" || layer.kind === "barcode";
  angle = square || shift ? Math.round(angle / (square ? 90 : 15)) * (square ? 90 : 15) : round1(angle);
  return ((angle % 360) + 360) % 360;
}
