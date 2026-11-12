/**
 * The box-opening animation, solved from the brand symbol's own geometry (no guessed shapes).
 *
 * The symbol (136 x 126) is a box seen from above at 45 degrees: each of the four flaps lies flat
 * (rotation 0) outward from one rim edge. A flap is a parallelogram: `h1 -> h2` is its hinge on the
 * rim, `m` is the screen vector from the hinge to its outer edge. Swinging a flap by `deg` about its
 * hinge keeps the hinge fixed and turns `m` into `m' = (m.x cos, m.y cos - LIFT sin)`: the outward
 * part shrinks with cos and the flap rises on screen by LIFT (one flap depth, 0.452 of the box side,
 * times the vertical unit 44.8) with sin. 180 degrees folds the flap back over the opening.
 * Because that map is affine, the exact brand path is moved with one `matrix()`; at 0 degrees the
 * matrix is the identity, so the last frame is the static logo by construction.
 */
export type FlapKey = "tl" | "tr" | "bl" | "br";
type Pt = readonly [number, number];
type Hinge = { h1: Pt; h2: Pt; m: Pt };

export const FLAP_KEYS: readonly FlapKey[] = ["tl", "tr", "bl", "br"];
/**
 * Document (paint) order, bottom to top. The staggered closing order is tl/br, bl, then tr.
 * Four quarter panels stay visible on the lid instead of hiding the earlier pair beneath the later pair.
 * Opened, tr lies at the back, where the front flaps and a lifting tl/br must cover it, so tr is drawn twice:
 * layer 0 (bottom) while it is at most LAYER_DEG, layer 1 (top) beyond. The swap happens while tr overlaps
 * no other flap, so it never shows.
 */
export const FLAP_SLOTS: readonly { key: FlapKey; layer?: 0 | 1 }[] = [
  { key: "tr", layer: 0 }, { key: "tl" }, { key: "br" }, { key: "bl" }, { key: "tr", layer: 1 },
];
const LAYER_DEG = 90;
export const flapLayer = (deg: number): 0 | 1 => (deg > LAYER_DEG ? 1 : 0);
const LIFT = 20.25;
const rad = (deg: number) => (deg * Math.PI) / 180;

export const HINGES: Record<FlapKey, Hinge> = {
  tl: { h1: [65.44, 15.0], h2: [21.26, 46.5], m: [-20.3, -14.4] },
  tr: { h1: [69.85, 15.0], h2: [114.03, 46.5], m: [20.3, -14.4] },
  bl: { h1: [21.26, 48.95], h2: [65.9, 80.6], m: [-20.5, 14.4] },
  br: { h1: [114.03, 48.95], h2: [69.39, 80.6], m: [20.5, 14.4] },
};

const num = (value: number) => Math.round(value * 1000) / 1000;
const sub = (a: Pt, b: Pt): Pt => [a[0] - b[0], a[1] - b[1]];
const cross = (a: Pt, b: Pt) => a[0] * b[1] - a[1] * b[0];

/**
 * Shut, opposing flaps must overlap or the interior shows through a slot down the middle of the lid. The hinges
 * sit a little outside the rim, so a flap folded at its own depth reaches only 47.1 of the 55.9 units between
 * opposite hinges. SHUT_K stretches the flap depth until each opposite pair overlaps by SHUT_OVERLAP.
 */
const SHUT_OVERLAP = 1.2;
function reachNeeded(a: FlapKey, b: FlapKey): number {
  const dir = sub(HINGES[a].h2, HINGES[a].h1);
  const n: Pt = [-dir[1] / Math.hypot(...dir), dir[0] / Math.hypot(...dir)];
  const dot = (p: Pt) => p[0] * n[0] + p[1] * n[1];
  const gap = Math.abs(dot(sub(HINGES[b].h1, HINGES[a].h1)));
  return (gap + SHUT_OVERLAP) / (Math.abs(dot(HINGES[a].m)) + Math.abs(dot(HINGES[b].m)));
}
export const SHUT_K = Math.max(reachNeeded("tl", "br"), reachNeeded("tr", "bl"));

/**
 * While shut the lid must be one clean rhombus: opposing flaps overlap at the seam (SHUT_K) and the lid rides 1.6
 * units above the body so the edge line between lid and faces stays visible. Both ease in over the last 30 degrees.
 */
const closedness = (deg: number) => Math.min(1, Math.max(0, (deg - 150) / 30));

/**
 * Extend the hinge ends to their neighbouring hinge intersections before dividing the lid into quarters.
 * tl's back tip stays inset: extending it into the top corner clips the tr flap as it starts folding.
 * Its opposite end and the other hinges extend to keep the panels joined, including the central seam.
 */
function widen(key: FlapKey): readonly [number, number] {
  const { h1, h2 } = HINGES[key];
  const h = sub(h2, h1), len = Math.hypot(...h);
  const reach = (end: Pt) => {
    let best = 0;
    for (const other of FLAP_KEYS) {
      if (other === key || (other === "tl" && key === "br") || (other === "br" && key === "tl")
        || (other === "tr" && key === "bl") || (other === "bl" && key === "tr")) continue;
      const o = HINGES[other], d = sub(o.h2, o.h1);
      if (Math.min(Math.hypot(...sub(o.h1, end)), Math.hypot(...sub(o.h2, end))) > 6) continue;
      // Parameter along h where this hinge line crosses the other one.
      const s = cross(sub(o.h1, h1), d) / cross(h, d);
      best = Math.max(best, end === h1 ? -s * len : (s - 1) * len);
    }
    return best;
  };
  return [reach(h1), reach(h2)];
}
const WIDEN = Object.fromEntries(FLAP_KEYS.map(key => [key, key === "tl" ? [0, widen(key)[1]] : widen(key)])) as Record<FlapKey, readonly [number, number]>;

/** `matrix(a,b,c,d,e,f)` swinging the flap `deg` about its hinge, or "none" when it is at rest. */
export function flapTransform(key: FlapKey, deg: number): string {
  if (Math.abs(deg) < 0.01) return "none";
  const { h1, h2, m } = HINGES[key];
  const shut = closedness(deg), h = sub(h2, h1), len = Math.hypot(...h);
  const [before, after] = WIDEN[key].map(v => v * shut);
  // Four quarter panels: shorten each hinge towards its own corner as the lid closes.
  // The opposite pair uses the other half, tiling the rhombus around one shared centre.
  const span = 1 + (before + after) / len;
  const hp: Pt = [h[0] * span * (1 - 0.5 * shut), h[1] * span * (1 - 0.5 * shut)];
  const slide = (key === "tr" || key === "br" ? 0.5 * shut * span : 0) - before / len;
  const k = 1 + (SHUT_K - 1) * shut;
  return affine(h, hp, m, swung(key, deg, k), h1, [h[0] * slide, h[1] * slide - 1.6 * shut]);
}
const swung = (key: FlapKey, deg: number, k = 1): Pt => {
  const { m } = HINGES[key];
  return [k * m[0] * Math.cos(rad(deg)), k * (m[1] * Math.cos(rad(deg)) - LIFT * Math.sin(rad(deg)))];
};

/** Linear map L with L h = hp and L m = mp, as a CSS matrix pivoting on `origin`, then shifted by `shift`. */
function affine(h: Pt, hp: Pt, m: Pt, mp: Pt, origin: Pt, shift: Pt): string {
  const det = h[0] * m[1] - m[0] * h[1];
  // Inverse of [h m] (columns): (1/det) [[m1, -m0], [-h1, h0]].
  const i00 = m[1] / det, i01 = -m[0] / det, i10 = -h[1] / det, i11 = h[0] / det;
  // L = [hp mp] * inverse.
  const a = hp[0] * i00 + mp[0] * i10;
  const c = hp[0] * i01 + mp[0] * i11;
  const b = hp[1] * i00 + mp[1] * i10;
  const d = hp[1] * i01 + mp[1] * i11;
  const e = origin[0] - (a * origin[0] + c * origin[1]) + shift[0];
  const f = origin[1] - (b * origin[0] + d * origin[1]) + shift[1];
  const dp = (value: number, places: number) => String(Number(value.toFixed(places)));
  return `matrix(${[a, b, c, d].map(v => dp(v, 4)).join(",")},${dp(e, 2)},${dp(f, 2)})`;
}

/**
 * Signed on-screen area of the swung flap relative to its resting area: 1 at rest, 0 edge-on, negative once the
 * other face is turned to the viewer. Back flaps (tl, tr) go edge-on near 126 degrees, front flaps (bl, br) near 56.
 */
export function flapArea(key: FlapKey, deg: number): number {
  const h = sub(HINGES[key].h2, HINGES[key].h1);
  return cross(h, swung(key, deg)) / cross(h, HINGES[key].m);
}

const clamp = (value: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, value));
const easeInOut = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
/** Both sides retain the flap's own brand colour throughout the fold (SW-389). */
export function flapFace(key: FlapKey, deg: number): { side: "inner" | "outer"; shade: number } {
  return { side: flapArea(key, deg) <= 0 ? "outer" : "inner", shade: 0 };
}

type Schedule = { lift: number; spring: number; end: number; decay: number; cycles: number };
/** The top flap (tr) starts first, alone, then bl (now on top); the inner pair (tl, br) follows. Back flaps wobble less than front ones. */
const SCHEDULE: Record<FlapKey, Schedule> = {
  tr: { lift: 0.07, spring: 0.19, end: 0.84, decay: 4.2, cycles: 0.75 },
  bl: { lift: 0.19, spring: 0.25, end: 0.83, decay: 4.6, cycles: 1.1 },
  tl: { lift: 0.24, spring: 0.31, end: 0.9, decay: 4.2, cycles: 0.75 },
  br: { lift: 0.24, spring: 0.31, end: 0.88, decay: 4.6, cycles: 1.1 },
};
const LIFT_DEG = 38;

/** Flap angle (degrees, 180 closed .. 0 open) at normalised time t of the one-shot opening. */
export function openAngle(key: FlapKey, t: number): number {
  const s = SCHEDULE[key];
  if (t <= s.lift) return 180;
  if (t < s.spring) return 180 - LIFT_DEG * easeInOut((t - s.lift) / (s.spring - s.lift));
  if (t >= s.end) return 0;
  const p = (t - s.spring) / (s.end - s.spring);
  const tail = Math.exp(-s.decay) * Math.cos(2 * Math.PI * s.cycles);
  // Damped spring 0 -> 1 with overshoot; the p^6 term lands it exactly on 1 at the end.
  const g = 1 - Math.exp(-s.decay * p) * Math.cos(2 * Math.PI * s.cycles * p) + tail * Math.pow(p, 6);
  return (180 - LIFT_DEG) * (1 - g);
}

/**
 * Folding shut, a flap at the same angle as its neighbour would pass through it (two flaps past 90 degrees on
 * adjacent edges intersect), so the fold is staggered in paint order: the inner pair (tl, br) is down before bl
 * passes upright, and bl is down before tr does. Each flap folds over half of the fold time.
 */
const FOLD: Record<FlapKey, readonly [number, number]> = { tl: [0, 0.5], br: [0, 0.5], bl: [0.25, 0.75], tr: [0.5, 1] };
export function foldAngle(key: FlapKey, p: number): number {
  const [from, to] = FOLD[key];
  return 180 * easeInOut(clamp((p - from) / (to - from)));
}

/** Loader cycle: open (the one-shot), hold open, fold shut, hold shut. */
export function loopAngle(key: FlapKey, t: number): number {
  if (t < 0.36) return openAngle(key, t / 0.36);
  if (t < 0.62) return 0;
  if (t < 0.84) return foldAngle(key, (t - 0.62) / 0.22);
  return 180;
}
/**
 * Hover/focus cycle: starts at the resting (open) logo, folds shut (the loader's fold, shorter), then plays the
 * one-shot opening, ending on the resting logo again. No hold, so no snap at either end.
 * `fold` is the fraction of the cycle spent folding.
 */
export function hoverAngle(key: FlapKey, t: number, fold: number): number {
  if (t < fold) return foldAngle(key, t / fold);
  return openAngle(key, (t - fold) / (1 - fold));
}

/** The lighter interior wall shows while the box is part open and fades to nothing at rest and when shut. */
export function wallOpacity(angles: number[]): number {
  const mean = angles.reduce((sum, value) => sum + value, 0) / angles.length;
  return num(clamp(mean / 25) * clamp((172 - mean) / 25));
}

/** True when any flap has left its resting place (the reversed artwork then needs its cap and flap outlines). */
export const moving = (angles: number[]) => angles.some(deg => Math.abs(deg) >= 0.01);

/** Motion arcs follow how fast a flap is turning (restrained: at most 0.8). */
export function arcOpacity(speed: number, peak: number): number {
  return num(clamp(speed / peak * 1.3 - 0.25) * 0.8);
}
