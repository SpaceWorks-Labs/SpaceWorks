import {
  FLAP_KEYS, arcOpacity, flapArea, flapFace, flapLayer, flapTransform, hoverAngle, loopAngle, moving, openAngle, wallOpacity,
  type FlapKey,
} from "./v200Geometry";

/** Duration of the one-shot opening (ms) and of one loader cycle (ms). */
export const OPEN_MS = 1600;
export const LOOP_MS = 4400;
/** Hover/focus cycle: fold shut (FOLD_MS) then the one-shot opening (OPEN_MS); starts and ends on the resting logo. */
export const FOLD_MS = 600;
export const HOVER_MS = FOLD_MS + OPEN_MS;
/**
 * Flap keyframes are dense (one per frame at 60 fps for the opening) and played with steps(1,end): browsers
 * interpolate two matrix() values by decomposing them, which drifts the hinge and glitches near edge-on, so
 * no flap matrix is ever interpolated. The cap and the tr layer swap are steps on the same grid, so they change
 * on exactly the frame the flaps do. Only the wall and arc opacities interpolate linearly.
 */
const SAMPLES = 96;
const LOOP_SAMPLES = 160;
const pct = (i: number, n = SAMPLES) => `${Math.round((i / n) * 10000) / 100}%`;
type AngleFn = (key: FlapKey, t: number) => number;
const anglesAt = (angle: AngleFn, t: number) => FLAP_KEYS.map(key => angle(key, t));
const n3 = (value: number) => String(Math.round(value * 1000) / 1000);

/** Inner face: the logo colour, shaded towards the under-colour; outer face: `--alt`. */
function fill(key: FlapKey, deg: number): string {
  const { side, shade } = flapFace(key, deg);
  if (side === "outer") return "var(--alt)";
  if (shade <= 0) return "var(--c)";
  if (shade >= 1) return "var(--sw-under)";
  return `color-mix(in srgb,var(--sw-under) ${Math.round(shade * 1000) / 10}%,var(--c))`;
}

/**
 * A moving flap is outlined in the ground colour (`--sw-ground`), drawn under its fill (paint-order: stroke), the
 * way both masters separate their parts with ground-coloured gaps; without it a teal flap melts into the teal
 * face behind it, and a cream flap into the cream cap. The reversed artwork switches it on with its cap, on the
 * first frame anything moves (`--sw-gap-w`); the light artwork has no cap and fades it in over the first
 * RAMP_DEG degrees (`--sw-ramp-w`), so the resting logo and the first frames match. Both thin out near edge-on,
 * where the flap is a sliver and a full outline would read as a cut.
 */
const RAMP_DEG = 12;
function strokeWidth(key: FlapKey, deg: number, live: boolean): string {
  const thin = Math.min(1, Math.abs(flapArea(key, deg)) / 0.3);
  const gap = live ? thin : 0;
  const ramp = Math.min(1, Math.abs(deg) / RAMP_DEG) * thin;
  if (!gap && !ramp) return "0";
  return `calc(${n3(gap)} * var(--sw-gap-w) + ${n3(ramp)} * var(--sw-ramp-w))`;
}

function flapKeyframes(name: string, key: FlapKey, angle: AngleFn, n: number): string {
  const rows: string[] = [];
  let previous = "";
  for (let i = 0; i <= n; i++) {
    const t = i / n, deg = angle(key, t);
    const body = `transform:${flapTransform(key, deg)};fill:${fill(key, deg)};stroke-width:${strokeWidth(key, deg, moving(anglesAt(angle, t)))}`;
    if (body !== previous || i === n) rows.push(`${pct(i, n)}{${body}}`);
    previous = body;
  }
  return `@keyframes ${name}-${key}{${rows.join("")}}`;
}

/** Opacity 0/1 keyframes (played with steps), emitted only where the value changes. */
function stepKeyframes(name: string, on: (t: number) => boolean, n: number): string {
  const rows: string[] = [];
  let previous: boolean | undefined;
  for (let i = 0; i <= n; i++) {
    const value = on(i / n);
    if (value !== previous || i === n) rows.push(`${pct(i, n)}{opacity:${value ? 1 : 0}}`);
    previous = value;
  }
  return `@keyframes ${name}{${rows.join("")}}`;
}

// Every sample is emitted: opacity keyframes interpolate linearly, so dropping unchanged samples would smear a ramp across the gap.
function curveKeyframes(name: string, value: (t: number) => number, n = SAMPLES): string {
  const rows: string[] = [];
  for (let i = 0; i <= n; i++) rows.push(`${pct(i, n)}{opacity:${value(i / n)}}`);
  return `@keyframes ${name}{${rows.join("")}}`;
}

const meanWall = (angle: AngleFn) => (t: number) => wallOpacity(anglesAt(angle, t));
function arcCurve(key: FlapKey, angle: AngleFn = openAngle, from = 0) {
  const dt = 1 / 400;
  const speed = (t: number) => Math.abs(angle(key, t + dt) - angle(key, t)) / dt;
  let peak = 0;
  for (let i = Math.floor(from * 400); i < 400; i++) peak = Math.max(peak, speed(i / 400));
  // `from`: arcs only show while opening, so the fold that precedes the opening stays dark.
  return (t: number) => (t > 0.97 || t < from ? 0 : arcOpacity(speed(t), peak));
}

/** Flaps, tr's two layers, the cap and the wall of one cycle: every channel sampled on the same grid. */
function cycle(name: string, mode: string, ms: number, iteration: string, angle: AngleFn, n: number): string {
  const steps = `${ms}ms steps(1,end) ${iteration}`;
  const run = FLAP_KEYS.map(key => `.sw-box.${mode} .f-${key}{animation:${name}-${key} ${steps}}`).join("")
    + ([0, 1] as const).map(z => `.sw-box.${mode} .f-tr.z${z}{animation:${name}-tr ${steps},${name}-tr-z${z} ${steps}}`).join("")
    + `.sw-box.${mode} .w{animation:${name}-w ${ms}ms linear ${iteration}}.sw-box.${mode} .p{animation:${name}-p ${steps}}`;
  const frames = FLAP_KEYS.map(key => flapKeyframes(name, key, angle, n)).join("")
    + ([0, 1] as const).map(z => stepKeyframes(`${name}-tr-z${z}`, t => flapLayer(angle("tr", t)) === z, n)).join("")
    + stepKeyframes(`${name}-p`, t => moving(anglesAt(angle, t)), n) + curveKeyframes(`${name}-w`, meanWall(angle), n);
  return run + frames;
}

const BASE = `.sw-box{position:relative;--sw-under:#354845;--sw-spark:#142C2A}
html.dark .sw-box{--sw-under:#66625D;--sw-spark:#FFF4E8}
.sw-box svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.sw-box .dk,html.dark .sw-box .lt{display:none}
html.dark .sw-box .dk{display:block}
.sw-box .f{transform-origin:0 0;stroke:var(--sw-ground,#FFF4E8);stroke-width:0;stroke-linejoin:round;paint-order:stroke;--sw-gap-w:0px;--sw-ramp-w:3.8px}
.sw-box .dk .f{stroke:var(--sw-ground,#000);--sw-gap-w:3.8px;--sw-ramp-w:0px}
.sw-box .f.z1{opacity:0}
.sw-box .w{fill:#354845;opacity:0}
html.dark .sw-box .w{fill:#FFF4E8;fill-opacity:.14}
.sw-box .a,.sw-box .k,.sw-box .r,.sw-box .p{opacity:0}
.sw-box .a,.sw-box .r{fill:none;stroke:var(--sw-spark);stroke-width:1.1;stroke-linecap:round}
.sw-box .k{fill:var(--sw-spark);transform-box:fill-box;transform-origin:center}
@keyframes sw-box-spark{0%,66%{opacity:0;transform:scale(.3)}77%{opacity:1;transform:scale(1.15)}85%{transform:scale(1)}91%{opacity:1}100%{opacity:0;transform:scale(1)}}
@keyframes sw-box-tick{0%,64%{opacity:0}74%,88%{opacity:1}100%{opacity:0}}
@media (prefers-reduced-motion:reduce){.sw-box .f,.sw-box .w,.sw-box .p,.sw-box .a,.sw-box .k,.sw-box .r{animation:none!important}}`;

function once(): string {
  const arcs = FLAP_KEYS.map(key => `.sw-box.once .a-${key}{animation:sw-box-a-${key} ${OPEN_MS}ms linear both}`).join("")
    + `.sw-box.once .k{animation:sw-box-spark ${OPEN_MS}ms ease-out both}.sw-box.once .r{animation:sw-box-tick ${OPEN_MS}ms linear both}`
    + FLAP_KEYS.map(key => curveKeyframes(`sw-box-a-${key}`, arcCurve(key))).join("");
  return cycle("sw-box", "once", OPEN_MS, "both", openAngle, SAMPLES) + arcs;
}

function loop(): string {
  return cycle("sw-boxl", "loop", LOOP_MS, "infinite", loopAngle, LOOP_SAMPLES);
}

/**
 * Hover/focus cycle (`.sw-box.hov`): fold shut, then open, no hold. Same generators as the loader and the
 * opening; the sparks reuse the opening's timing remapped onto the opening part of the cycle.
 */
function hover(): string {
  const fold = FOLD_MS / HOVER_MS;
  const angle: AngleFn = (key, t) => hoverAngle(key, t, fold);
  const at = (p: number) => `${Math.round((fold + (1 - fold) * p) * 10000) / 100}%`;
  const N = 132;
  const fx = FLAP_KEYS.map(key => `.sw-box.hov .a-${key}{animation:sw-boxh-a-${key} ${HOVER_MS}ms linear both}`).join("")
    + `.sw-box.hov .k{animation:sw-boxh-spark ${HOVER_MS}ms ease-out both}.sw-box.hov .r{animation:sw-boxh-tick ${HOVER_MS}ms linear both}`;
  const sparks = `@keyframes sw-boxh-spark{0%,${at(0.66)}{opacity:0;transform:scale(.3)}${at(0.77)}{opacity:1;transform:scale(1.15)}${at(0.85)}{transform:scale(1)}${at(0.91)}{opacity:1}100%{opacity:0;transform:scale(1)}}`
    + `@keyframes sw-boxh-tick{0%,${at(0.64)}{opacity:0}${at(0.74)},${at(0.88)}{opacity:1}100%{opacity:0}}`;
  const arcs = FLAP_KEYS.map(key => curveKeyframes(`sw-boxh-a-${key}`, arcCurve(key, angle, fold), N)).join("");
  return cycle("sw-boxh", "hov", HOVER_MS, "both", angle, N) + fx + sparks + arcs;
}

/** All box CSS. `mode` limits it to what a host needs (index.html only plays the one-shot). */
export function boxOpenCss(mode: "once" | "all" = "all"): string {
  return [BASE, once(), mode === "all" ? `${loop()}
${hover()}` : ""].join("\n");
}

/**
 * Single-colour layer over the same markup and keyframes, for use inside buttons: every face is the
 * host's `currentColor` at a different strength (the flap keyframes read `--c`/`--alt`/`--sw-under`, so
 * overriding those keeps the animation and the cube read). Only the light artwork is shown. Not part of
 * the splash, so index.html stays untouched.
 */
export function boxMonoCss(): string {
  const mix = (n: number) => `color-mix(in srgb,currentColor ${n}%,transparent)`;
  return `.sw-box.mono{--sw-under:${mix(35)}!important;--sw-spark:currentColor}
.sw-box.mono .dk{display:none!important}.sw-box.mono .lt{display:block!important}
.sw-box.mono svg>path:not(.f){fill:currentColor!important}
.sw-box.mono svg>path:not(.f):nth-child(1){fill-opacity:.45}.sw-box.mono svg>path:not(.f):nth-child(2){fill-opacity:.7}
.sw-box.mono .c{fill-opacity:1}
.sw-box.mono .f{--c:currentColor!important;--alt:currentColor!important;--sw-gap-w:0px;--sw-ramp-w:0px}
.sw-box.mono .w{fill:currentColor!important;fill-opacity:.25}`;
}

/**
 * Forced grounds for the logo hover cycle: `g-dark` draws the reversed artwork on a surface that is always dark,
 * `g-light` the light artwork on a surface that is always light, whatever `html.dark` says. The flap outlines
 * follow the artwork (`.lt`/`.dk`), so only the theme colours need forcing here.
 */
export function boxGroundCss(): string {
  return `.sw-box.g-dark{--sw-under:#66625D;--sw-spark:#FFF4E8}
.sw-box.g-dark .lt{display:none}.sw-box.g-dark .dk{display:block}.sw-box.g-dark .w{fill:#FFF4E8;fill-opacity:.14}
html.dark .sw-box.g-light{--sw-under:#354845;--sw-spark:#142C2A}
html.dark .sw-box.g-light .dk{display:none}html.dark .sw-box.g-light .lt{display:block}html.dark .sw-box.g-light .w{fill:#354845;fill-opacity:1}`;
}
