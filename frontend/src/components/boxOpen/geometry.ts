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

/** Bottom-to-top draw order while closed: tr (orange) ends up on top of the folded lid. */
export const FLAP_ORDER: readonly FlapKey[] = ["bl", "tl", "br", "tr"];
export const FLAP_KEYS: readonly FlapKey[] = ["tl", "tr", "bl", "br"];
const LIFT = 20.25;
const rad = (deg: number) => (deg * Math.PI) / 180;

export const HINGES: Record<FlapKey, Hinge> = {
  tl: { h1: [65.44, 15.0], h2: [21.26, 46.5], m: [-20.3, -14.4] },
  tr: { h1: [69.85, 15.0], h2: [114.03, 46.5], m: [20.3, -14.4] },
  bl: { h1: [21.26, 48.95], h2: [65.9, 80.6], m: [-20.5, 14.4] },
  br: { h1: [114.03, 48.95], h2: [69.39, 80.6], m: [20.5, 14.4] },
};

const num = (value: number) => Math.round(value * 1000) / 1000;

/**
 * While shut the lid must be one clean rhombus: opposing flaps overlap slightly at the seam (`k` stretches the
 * flap depth from 0.452 to 0.515 of the box side), so no interior shows, and the lid rides 1.6 units above the body
 * so the cream edge line between lid and faces stays visible. Both ease in over the last 30 degrees of the fold.
 */
const closedness = (deg: number) => Math.min(1, Math.max(0, (deg - 150) / 30));

/** `matrix(a,b,c,d,e,f)` swinging the flap `deg` about its hinge, or "none" when it is at rest. */
export function flapTransform(key: FlapKey, deg: number): string {
  if (Math.abs(deg) < 0.01) return "none";
  const { h1, h2, m } = HINGES[key];
  const h: Pt = [h2[0] - h1[0], h2[1] - h1[1]];
  const c = Math.cos(rad(deg));
  const sn = Math.sin(rad(deg));
  const shut = closedness(deg);
  const k = 1 + 0.14 * shut;
  return affine(h, m, [k * m[0] * c, k * (m[1] * c - LIFT * sn)], h1, -1.6 * shut);
}

/** Linear map L with L h = h and L m = mp, as a CSS matrix pivoting on `origin`. */
function affine(h: Pt, m: Pt, mp: Pt, origin: Pt, dy = 0): string {
  const det = h[0] * m[1] - m[0] * h[1];
  // Inverse of [h m] (columns): (1/det) [[m1, -m0], [-h1, h0]].
  const i00 = m[1] / det, i01 = -m[0] / det, i10 = -h[1] / det, i11 = h[0] / det;
  // L = [h mp] * inverse.
  const a = h[0] * i00 + mp[0] * i10;
  const c = h[0] * i01 + mp[0] * i11;
  const b = h[1] * i00 + mp[1] * i10;
  const d = h[1] * i01 + mp[1] * i11;
  const e = origin[0] - (a * origin[0] + c * origin[1]);
  const f = origin[1] - (b * origin[0] + d * origin[1]) + dy;
  const dp = (value: number, places: number) => String(Number(value.toFixed(places)));
  return `matrix(${[a, b, c, d].map(v => dp(v, 4)).join(",")},${dp(e, 2)},${dp(f, 2)})`;
}

const clamp = (value: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, value));
const easeInOut = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);

type Schedule = { lift: number; spring: number; end: number; decay: number; cycles: number };
/** The orange flaps (tr, then bl) start first, alone; the teal pair (tl, br) follows. Back flaps wobble less than front ones. */
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

/** Loader cycle: open (the one-shot), hold open, fold shut together, hold shut. */
export function loopAngle(key: FlapKey, t: number): number {
  if (t < 0.36) return openAngle(key, t / 0.36);
  if (t < 0.62) return 0;
  if (t < 0.84) return 180 * easeInOut((t - 0.62) / 0.22);
  return 180;
}

/** The face a flap shows at an angle: its brand colour, the dark inner face (back flaps standing up), or teal (bl folded over). */
export function flapFace(key: FlapKey, deg: number): "c" | "under" | "alt" {
  if ((key === "tl" || key === "tr") && deg > 62 && deg < 128) return "under";
  if (key === "bl" && deg > 105) return "alt";
  return "c";
}

/** The lighter interior wall shows while the box is part open and fades to nothing at rest and when shut. */
export function wallOpacity(angles: number[]): number {
  const mean = angles.reduce((sum, value) => sum + value, 0) / angles.length;
  return num(clamp(mean / 25) * clamp((172 - mean) / 25));
}

/** The reversed (dark) body has no top face, so while the lid is shut a cream cap fills the gap under it; it goes once the teal pair (tl, br) opens. */
export function capOpacity(angles: number[]): number {
  const mean = angles.reduce((sum, value) => sum + value, 0) / angles.length;
  return num(clamp((mean - 150) / 15));
}

/** Motion arcs follow how fast a flap is turning (restrained: at most 0.8). */
export function arcOpacity(speed: number, peak: number): number {
  return num(clamp(speed / peak * 1.3 - 0.25) * 0.8);
}
