/**
 * Pure geometry and colour helpers for the cover editor (parity E-F3, B4). Nothing here touches the DOM, so the
 * crop stage (a CSS transform) and the canvas renderer share one model and the unit tests can check it.
 *
 * Model, in output pixels with y pointing down:
 *   frame point = centre + R(angle) · [ pan + flip · (scale · image point) ]
 * `scale` is the smallest one at which the rotated image still covers the whole frame, times `zoom` (>= 1).
 * `pan` is kept as a -1..1 share of the room the zoom leaves on each image axis, so no setting can ever pull
 * an empty edge into the frame.
 */
export type CoverShape = "banner" | "wide" | "square";
export type CoverLook = "original" | "vivid" | "warm" | "cool" | "mono" | "soft";
export type CoverEdits = {
  shape: CoverShape; rotation: number; straighten: number; flipX: boolean; flipY: boolean;
  zoom: number; panX: number; panY: number; brightness: number; contrast: number; saturation: number; look: CoverLook;
};
export const SHAPES: Record<CoverShape, { width: number; height: number; ratio: string }> = {
  banner: { width: 1680, height: 735, ratio: "16:7" },
  wide: { width: 1600, height: 900, ratio: "16:9" },
  square: { width: 1200, height: 1200, ratio: "1:1" },
};
export const SHAPE_ORDER: CoverShape[] = ["banner", "wide", "square"];
export const DEFAULT_COVER_EDITS: CoverEdits = {
  shape: "banner", rotation: 0, straighten: 0, flipX: false, flipY: false, zoom: 1, panX: 0, panY: 0,
  brightness: 0, contrast: 0, saturation: 0, look: "original",
};
export const MAX_ZOOM = 4;
export const RANGES = { straighten: [-15, 15], brightness: [-50, 50], contrast: [-50, 50], saturation: [-100, 100] } as const;

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

/** Where the same picture is centre-cropped elsewhere: the event page header, cards and social previews. */
export const CROP_GUIDES = [{ id: "page", aspect: 16 / 7 }, { id: "cards", aspect: 2.5 }, { id: "social", aspect: 1.91 }] as const;
export type CropGuideId = typeof CROP_GUIDES[number]["id"];

/** The centred region (fractions of the frame) an `object-cover` box of `crop` keeps from a frame of `frame`. */
export function guideRect(frame: number, crop: number) {
  if (crop >= frame) { const height = frame / crop; return { left: 0, top: (1 - height) / 2, width: 1, height }; }
  const width = crop / frame;
  return { left: (1 - width) / 2, top: 0, width, height: 1 };
}

export function guidesFor(shape: CoverShape) {
  const frame = SHAPES[shape].width / SHAPES[shape].height;
  return CROP_GUIDES.filter(guide => Math.abs(guide.aspect - frame) / frame > 0.02)
    .map(guide => ({ id: guide.id as CropGuideId, ...guideRect(frame, guide.aspect) }));
}

/** Scale, rotation, pan offset (in image axes) and flips for an image of `width` x `height`. */
export function placement(edits: CoverEdits, width: number, height: number) {
  const { width: W, height: H } = SHAPES[edits.shape];
  const angle = ((edits.rotation + edits.straighten) * Math.PI) / 180;
  const cos = Math.abs(Math.cos(angle)), sin = Math.abs(Math.sin(angle));
  // The frame's bounding box measured along the image's own axes.
  const boxW = cos * W + sin * H, boxH = sin * W + cos * H;
  const scale = Math.max(boxW / width, boxH / height) * clamp(edits.zoom, 1, MAX_ZOOM);
  const slackX = Math.max(0, (width * scale - boxW) / 2), slackY = Math.max(0, (height * scale - boxH) / 2);
  return { W, H, angle, scale, slackX, slackY, panX: clamp(edits.panX, -1, 1) * slackX, panY: clamp(edits.panY, -1, 1) * slackY,
    flipX: edits.flipX ? -1 : 1, flipY: edits.flipY ? -1 : 1 };
}

/** Move the picture by a drag of (dx, dy) frame pixels; returns the new pan shares. */
export function dragPan(edits: CoverEdits, width: number, height: number, dx: number, dy: number) {
  const place = placement(edits, width, height);
  const c = Math.cos(-place.angle), s = Math.sin(-place.angle);
  const du = c * dx - s * dy, dv = s * dx + c * dy;
  return {
    panX: place.slackX ? clamp(edits.panX + du / place.slackX, -1, 1) : 0,
    panY: place.slackY ? clamp(edits.panY + dv / place.slackY, -1, 1) : 0,
  };
}

/* ---------- Colour: a preset look first, then the slider changes ---------- */
type FilterFn = "brightness" | "contrast" | "saturate" | "sepia" | "grayscale" | "hue-rotate";
export type FilterOp = { fn: FilterFn; amount: number };
const LOOK_OPS: Record<CoverLook, FilterOp[]> = {
  original: [],
  vivid: [{ fn: "contrast", amount: 1.12 }, { fn: "saturate", amount: 1.35 }],
  warm: [{ fn: "sepia", amount: 0.22 }, { fn: "saturate", amount: 1.15 }, { fn: "brightness", amount: 1.03 }],
  cool: [{ fn: "hue-rotate", amount: 12 }, { fn: "saturate", amount: 0.9 }, { fn: "brightness", amount: 1.04 }],
  mono: [{ fn: "grayscale", amount: 1 }, { fn: "contrast", amount: 1.1 }],
  soft: [{ fn: "contrast", amount: 0.86 }, { fn: "brightness", amount: 1.06 }, { fn: "saturate", amount: 0.88 }],
};
export const LOOK_ORDER = Object.keys(LOOK_OPS) as CoverLook[];

export function filterOps(edits: Pick<CoverEdits, "look" | "brightness" | "contrast" | "saturation">): FilterOp[] {
  const ops = [...LOOK_OPS[edits.look]];
  const add = (fn: FilterFn, value: number, [min, max]: readonly [number, number]) => {
    const change = clamp(value, min, max);
    if (change) ops.push({ fn, amount: 1 + change / 100 });
  };
  add("brightness", edits.brightness, RANGES.brightness);
  add("contrast", edits.contrast, RANGES.contrast);
  add("saturate", edits.saturation, RANGES.saturation);
  return ops;
}

const round = (value: number) => Math.round(value * 1000) / 1000;
export function cssFilter(ops: FilterOp[]) {
  return ops.length ? ops.map(op => op.fn === "hue-rotate" ? `hue-rotate(${round(op.amount)}deg)` : `${op.fn}(${round(op.amount)})`).join(" ") : "none";
}

/** 3x4 colour matrix of one op (Filter Effects definitions), for browsers whose canvas has no `filter`. */
function matrix({ fn, amount: a }: FilterOp): number[] {
  const sat = (k: number) => [0.213 + 0.787 * k, 0.715 - 0.715 * k, 0.072 - 0.072 * k, 0, 0.213 - 0.213 * k, 0.715 + 0.285 * k,
    0.072 - 0.072 * k, 0, 0.213 - 0.213 * k, 0.715 - 0.715 * k, 0.072 + 0.928 * k, 0];
  if (fn === "brightness") return [a, 0, 0, 0, 0, a, 0, 0, 0, 0, a, 0];
  if (fn === "contrast") { const b = 0.5 - 0.5 * a; return [a, 0, 0, b, 0, a, 0, b, 0, 0, a, b]; }
  if (fn === "saturate") return sat(a);
  if (fn === "grayscale") return sat(1 - clamp(a, 0, 1));
  if (fn === "sepia") {
    const g = 1 - clamp(a, 0, 1);
    return [0.393 + 0.607 * g, 0.769 - 0.769 * g, 0.189 - 0.189 * g, 0, 0.349 - 0.349 * g, 0.686 + 0.314 * g, 0.168 - 0.168 * g, 0,
      0.272 - 0.272 * g, 0.534 - 0.534 * g, 0.131 + 0.869 * g, 0];
  }
  const r = (a * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r);
  return [0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928, 0,
    0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.14, 0.072 - c * 0.072 - s * 0.283, 0,
    0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072, 0];
}

/** Apply the ops to RGBA pixels in place, clamping after each op as the browser does. */
export function applyFilterOps(data: Uint8ClampedArray, ops: FilterOp[]) {
  const matrices = ops.map(matrix);
  for (let i = 0; i < data.length && matrices.length; i += 4) {
    let r = data[i] / 255, g = data[i + 1] / 255, b = data[i + 2] / 255;
    for (const m of matrices) {
      const nr = m[0] * r + m[1] * g + m[2] * b + m[3], ng = m[4] * r + m[5] * g + m[6] * b + m[7], nb = m[8] * r + m[9] * g + m[10] * b + m[11];
      r = clamp(nr, 0, 1); g = clamp(ng, 0, 1); b = clamp(nb, 0, 1);
    }
    data[i] = r * 255; data[i + 1] = g * 255; data[i + 2] = b * 255;
  }
  return data;
}
