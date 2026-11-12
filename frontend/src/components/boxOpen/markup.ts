import { logoMasters } from "../spaceWorksLogoPaths";
import { FLAP_KEYS, FLAP_SLOTS, type FlapKey } from "./geometry";

/**
 * The animated box as one SVG string, built from the brand masters (`symbol`, `symbol-reversed`) so the
 * paths are the logo's own. The same string is inlined in index.html (the pre-React splash) and rendered
 * by LogoLoader. Both themes are present; CSS shows the one for `html.dark`.
 */
const VIEW_BOX = "0 0 136 126";
/**
 * The light master's two full-height faces. The reversed master cuts its faces short under the front flaps, so the
 * moment a flap leaves its resting place the reversed box shows this cap (cream) behind it: no black hole opens in
 * the side of the box, and shut it reads as a solid cube.
 */
const CAP_FACES = logoMasters.symbol.paths.slice(0, 2);
const WALL = "67.5,17.2 111.5,47.8 67.5,78.9";
const star = (x: number, y: number, r: number) =>
  `<path class="k" d="M${x} ${y - r}Q${x} ${y} ${x + r} ${y}Q${x} ${y} ${x} ${y + r}Q${x} ${y} ${x - r} ${y}Q${x} ${y} ${x} ${y - r}Z"/>`;
const tick = (cx: number, cy: number, deg: number, from: number, to: number) => {
  const a = (deg * Math.PI) / 180;
  const p = (r: number) => `${Math.round((cx + r * Math.cos(a)) * 10) / 10} ${Math.round((cy + r * Math.sin(a)) * 10) / 10}`;
  return `<path class="r" d="M${p(from)}L${p(to)}"/>`;
};
const ARCS: Record<FlapKey, string> = {
  tr: "M133.5 7Q141.5 13 139.5 24M137 4Q148 12 145 27",
  tl: "M2.5 7Q-5.5 13 -3.5 24M-1 4Q-12 12 -9 27",
  bl: "M-2 72Q-9 82 -4 93M-5 69Q-14 81 -8 96",
  br: "M138 72Q145 82 140 93M141 69Q150 81 144 96",
};
const SPARKS = [star(121, 3, 6.5), star(-7, 47, 6), star(141, 45, 5),
  tick(67.5, -4, -90, 3, 10.5), tick(67.5, -4, -125, 3, 9), tick(67.5, -4, -55, 3, 9),
  tick(14, 4, -160, 3, 9), tick(14, 4, -125, 3, 9)].join("");

function variant(kind: "lt" | "dk"): string {
  const master = logoMasters[kind === "lt" ? "symbol" : "symbol-reversed"].paths;
  const flaps = master.slice(-4);
  const flapFill = (key: FlapKey) => logoMasters.symbol.paths.slice(-4)[FLAP_KEYS.indexOf(key)].fill;
  const body = master.slice(0, -4).map((path, index) =>
    `<path${index === 2 ? ' class="c"' : ""} fill="${path.fill}" d="${path.d}"/>`).join("");
  const flap = ({ key, layer }: (typeof FLAP_SLOTS)[number]) => {
    const path = flaps[FLAP_KEYS.indexOf(key)];
    const z = layer === undefined ? "" : ` z${layer}`;
    return `<path class="f f-${key}${z}" fill="${flapFill(key)}" style="--c:${flapFill(key)}" d="${path.d}"/>`;
  };
  const arcs = FLAP_KEYS.map(key => `<path class="a a-${key}" d="${ARCS[key]}"/>`).join("");
  return `<svg class="${kind}" viewBox="${VIEW_BOX}" aria-hidden="true" focusable="false">${body}`
    + `${kind === "dk" ? `<g class="p">${CAP_FACES.map(face => `<path fill="#FFF4E8" d="${face.d}"/>`).join("")}</g>` : ""}<polygon class="w" points="${WALL}"/>${FLAP_SLOTS.map(flap).join("")}<g class="x">${arcs}${SPARKS}</g></svg>`;
}

/** `<div class="sw-box once|loop">` markup for the given mode (no wrapper sizing: the host sets width/height). */
export function boxOpenSvg(): string {
  return variant("lt") + variant("dk");
}
