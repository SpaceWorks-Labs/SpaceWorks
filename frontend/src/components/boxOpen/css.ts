import {
  FLAP_KEYS, flapArea, flapLayer, flapTransform, hoverAngle, loopAngle, moving, openAngle, wallOpacity,
  type FlapKey,
} from "./geometry";
import { boxGroundCss as v200GroundCss, boxOpenCss as v200Css } from "./v200Css";
export { OPEN_MS, LOOP_MS, FOLD_MS, HOVER_MS, boxMonoCss } from "./v200Css";
import { OPEN_MS, LOOP_MS, FOLD_MS, HOVER_MS } from "./v200Css";

const SAMPLES = 96;
const pct = (i: number, n = SAMPLES) => `${Math.round(i / n * 10000) / 100}%`;
type AngleFn = (key: FlapKey, t: number) => number;
const anglesAt = (angle: AngleFn, t: number) => FLAP_KEYS.map(key => angle(key, t));
const n3 = (value: number) => String(Math.round(value * 1000) / 1000);

const RAMP_DEG = 12;
function strokeWidth(key: FlapKey, deg: number, live: boolean): string {
  const thin = Math.min(1, Math.abs(flapArea(key, deg)) / 0.3);
  const gap = live ? thin : 0;
  const ramp = Math.min(1, Math.abs(deg) / RAMP_DEG) * thin;
  if (!live || (!gap && !ramp)) return "0";
  return `calc(${n3(gap)} * var(--sw-gap-w) + ${n3(ramp)} * var(--sw-ramp-w))`;
}

function flapKeyframes(name: string, key: FlapKey, angle: AngleFn, n: number): string {
  const rows: string[] = [];
  let previous = "";
  for (let i = 0; i <= n; i++) {
    const t = i / n, deg = angle(key, t);
    const body = `transform:${flapTransform(key, deg)};fill:var(--c);stroke-width:${strokeWidth(key, deg, moving(anglesAt(angle, t)))}`;
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

/** Light-only overrides leave every v2.0.0 black-and-white keyframe intact. */
function cycle(name: string, mode: string, ms: number, iteration: string, angle: AngleFn, n: number): string {
  const steps = `${ms}ms steps(1,end) ${iteration}`;
  const target = `.sw-box.${mode} .colour`;
  return FLAP_KEYS.map(key => `${target} .f-${key}{animation:${name}-${key} ${steps}}`).join("")
    + ([0, 1] as const).map(z => `${target} .f-tr.z${z}{animation:${name}-tr ${steps},${name}-tr-z${z} ${steps}}`).join("")
    + `${target} .w{animation:${name}-w ${ms}ms linear ${iteration}}`
    + FLAP_KEYS.map(key => flapKeyframes(name, key, angle, n)).join("")
    + ([0, 1] as const).map(z => stepKeyframes(`${name}-tr-z${z}`, t => flapLayer(angle("tr", t)) === z, n)).join("")
    + stepKeyframes(`${name}-p`, t => moving(anglesAt(angle, t)), n)
    + curveKeyframes(`${name}-w`, t => wallOpacity(anglesAt(angle, t)), n);
}

/** Dark/reversed, mono and forced colours run the unchanged v2.0.0 animation. */
export function boxOpenCss(mode: "once" | "all" = "all"): string {
  const coloured = cycle("sw-box412", "once", OPEN_MS, "both", openAngle, SAMPLES)
    + (mode === "all" ? cycle("sw-box412l", "loop", LOOP_MS, "infinite", loopAngle, 160)
      + cycle("sw-box412h", "hov", HOVER_MS, "both", (key, t) => hoverAngle(key, t, FOLD_MS / HOVER_MS), 132) : "");
  return v200Css(mode) + "\n" + coloured
    + `
.sw-box .colour{display:none}
@media (forced-colors:none){
.sw-box:not(.mono) .lt{display:none!important}
html:not(.dark) .sw-box:not(.mono):not(.g-dark) .colour,html.dark .sw-box.g-light:not(.mono) .colour{display:block}
}
@media (forced-colors:active){.sw-box{--sw-ground:Canvas!important}.sw-box .f,.sw-box .p path,.sw-box .c,.sw-box svg>path{fill:CanvasText!important}}
@media (prefers-reduced-motion:reduce){.sw-box .colour .f,.sw-box .colour .w{animation:none!important}}`;
}

/** Keep the released stylesheet's ground section, including its export comment. */
export function boxGroundCss(): string {
  return "/* Ground overrides for the logo hover cycle (boxGroundCss): force the artwork for a surface that is always dark (g-dark) or light (g-light). */\n" + v200GroundCss();
}
