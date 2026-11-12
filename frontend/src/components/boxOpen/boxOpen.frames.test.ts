import { describe, expect, it } from "vitest";
import { logoMasters } from "../spaceWorksLogoPaths";
import { FOLD_MS, HOVER_MS, boxGroundCss, boxMonoCss, boxOpenCss } from "./css";
import {
  FLAP_KEYS, FLAP_SLOTS, HINGES, flapArea, flapFace, flapLayer, flapTransform, hoverAngle, loopAngle, moving, openAngle,
  type FlapKey,
} from "./geometry";
import { boxOpenSvg } from "./markup";

/**
 * The box's states, checked frame by frame against the generator (the pixel-level check of the same rules runs in
 * the design repo: scripts/check-box-frames.mjs, headless Edge). Shut: four visible regions, two orange and
 * two green. Rest: the static product logo. Every flap keeps its own colour; the cap and outlines appear
 * the moment anything moves, and flaps are painted in depth order.
 */
type Pt = [number, number];
const fold = FOLD_MS / HOVER_MS;
const CYCLES = {
  once: { name: "sw-box", angle: openAngle, n: 96 },
  loop: { name: "sw-boxl", angle: loopAngle, n: 160 },
  hov: { name: "sw-boxh", angle: (key: FlapKey, t: number) => hoverAngle(key, t, fold), n: 132 },
} as const;
const css = boxOpenCss();

/** The value a steps(1,end) keyframes block holds at sample i of n. */
const keyframeCache = new Map<string, { at: number; body: string }[]>();
function keyframeAt(name: string, i: number, n: number): string {
  let rows = keyframeCache.get(name);
  if (!rows) {
    const block = new RegExp(`@keyframes ${name}\\{((?:[\\d.]+%\\{[^}]*\\})+)\\}`).exec(css);
    if (!block) throw new Error(`no keyframes ${name}`);
    rows = [...block[1].matchAll(/([\d.]+)%\{([^}]*)\}/g)].map(row => ({ at: Number(row[1]), body: row[2] }));
    keyframeCache.set(name, rows);
  }
  const at = Math.round((i / n) * 10000) / 100;
  return rows.filter(row => row.at <= at + 1e-9).pop()!.body;
}

/** The flap's on-screen parallelogram at an angle (corners of its resting shape through its matrix). */
function polygon(key: FlapKey, deg: number): Pt[] {
  const { h1, h2, m } = HINGES[key];
  const corners: Pt[] = [[h1[0], h1[1]], [h2[0], h2[1]], [h2[0] + m[0], h2[1] + m[1]], [h1[0] + m[0], h1[1] + m[1]]];
  const matrix = /matrix\(([^)]+)\)/.exec(flapTransform(key, deg));
  if (!matrix) return corners;
  const [a, b, c, d, e, f] = matrix[1].split(",").map(Number);
  return corners.map(([x, y]) => [a * x + c * y + e, b * x + d * y + f]);
}
const inside = (poly: Pt[], [x, y]: Pt) => {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
};
/** The rim opening (the light master's top face), sampled on a grid and pulled 1 unit in from its edges. */
const RIM: Pt[] = [[67.64, 17.4], [110.6, 47.84], [67.64, 78.3], [24.7, 47.84]];
const rimPoints = () => {
  const points: Pt[] = [];
  for (let x = 20; x <= 116; x += 0.5) for (let y = 14; y <= 82; y += 0.5) if (inside(RIM, [x, y])) points.push([x, y]);
  return points;
};
const RIM_POINTS = rimPoints();
/** Topmost flap (in paint order) at a point, with every flap at its angle. */
function topmost(angles: Record<FlapKey, number>, point: Pt): FlapKey | undefined {
  let top: FlapKey | undefined;
  for (const slot of FLAP_SLOTS) {
    if (slot.layer !== undefined && slot.layer !== flapLayer(angles[slot.key])) continue;
    if (inside(polygon(slot.key, angles[slot.key]), point)) top = slot.key;
  }
  return top;
}
/**
 * Nearness to the viewer of a flap point (larger = nearer). The view is orthographic from the front, 45.5 degrees
 * above the rim plane (the symbol's rhombus is 89 wide and 63.5 tall): a point's plane position is its screen y
 * plus its lift, and nearness is plane position * cot + lift * tan.
 */
function depth(poly: Pt[], deg: number, point: Pt): number {
  const [p0, p1, , p3] = poly;
  const e1: Pt = [p1[0] - p0[0], p1[1] - p0[1]], e3: Pt = [p3[0] - p0[0], p3[1] - p0[1]];
  const det = e1[0] * e3[1] - e1[1] * e3[0];
  const v = (e1[0] * (point[1] - p0[1]) - e1[1] * (point[0] - p0[0])) / det;
  const lift = v * 20.25 * Math.sin((deg * Math.PI) / 180);
  const phi = (45.5 * Math.PI) / 180;
  return (point[1] + lift) / Math.tan(phi) + lift * Math.tan(phi);
}
const colour = (key: FlapKey) => (key === "tr" || key === "bl" ? "#FF7447" : "#006E63");

describe("box animation states", () => {
  it("shut: four visible flap regions cover the rim, two orange and two green", () => {
    const shut = { tl: 180, tr: 180, bl: 180, br: 180 };
    const seen = new Map<FlapKey, number>();
    for (const point of RIM_POINTS) {
      const top = topmost(shut, point);
      expect(top, `hole in the shut lid at ${point}`).toBeDefined();
      seen.set(top!, (seen.get(top!) ?? 0) + 1);
    }
    // Every flap owns a substantial region instead of being hidden under another panel.
    expect([...seen.keys()].sort()).toEqual(["bl", "br", "tl", "tr"]);
    for (const count of seen.values()) expect(count).toBeGreaterThan(1000);
    for (const key of FLAP_KEYS) expect(flapFace(key, 180).side).toBe("outer");
    expect([...seen.keys()].filter(key => colour(key) === "#FF7447").sort()).toEqual(["bl", "tr"]);
    expect([...seen.keys()].filter(key => colour(key) === "#006E63").sort()).toEqual(["br", "tl"]);
  });

  it("both themes give each flap its own solid brand colour on both sides", () => {
    for (const svg of boxOpenSvg().split("</svg>").slice(0, 2)) {
      for (const key of FLAP_KEYS) {
        const paths = [...svg.matchAll(new RegExp(`<path class="f f-${key}[^"]*"[^>]+>`, "g"))];
        expect(paths).toHaveLength(key === "tr" ? 2 : 1);
        for (const [path] of paths) expect(path).toContain(`fill="${colour(key)}" style="--c:${colour(key)}"`);
      }
      expect(svg).not.toContain("--alt");
      expect(svg).toContain('class="f f-tr z0"');
      expect(svg).toContain('class="f f-tr z1"');
    }
    expect(boxOpenSvg().split("</svg>")[1]).toContain('<g class="p">');
  });

  for (const [mode, cycle] of Object.entries(CYCLES)) {
    describe(mode, () => {
      const angles = (i: number) => FLAP_KEYS.map(key => cycle.angle(key, i / cycle.n));
      it("retains each flap colour throughout both faces of the fold", () => {
        for (const key of FLAP_KEYS) for (let i = 0; i < cycle.n; i++) {
          const a = cycle.angle(key, i / cycle.n), b = cycle.angle(key, (i + 1) / cycle.n);
          if (flapFace(key, a).side !== flapFace(key, b).side) {
            // The flap passed edge-on between the two samples: its area changed sign.
            expect(Math.sign(flapArea(key, a))).not.toBe(Math.sign(flapArea(key, b)));
          }
        }
        for (const key of ["tl", "tr"] as const) for (let deg = -30; flapArea(key, deg + 0.5) > 0; deg += 0.5) {
          expect(flapFace(key, deg).shade).toBe(0);
        }
      });
      it("shows the cap and the outlines on exactly the frames anything moves", () => {
        for (let i = 0; i <= cycle.n; i++) {
          const live = moving(angles(i));
          expect(keyframeAt(`${cycle.name}-p`, i, cycle.n)).toBe(`opacity:${live ? 1 : 0}`);
          for (const key of FLAP_KEYS) {
            const body = keyframeAt(`${cycle.name}-${key}`, i, cycle.n);
            expect(body.includes("transform:none")).toBe(!(Math.abs(cycle.angle(key, i / cycle.n)) >= 0.01));
            if (!live) expect(body).toContain("stroke-width:0");
            else if (Math.abs(flapArea(key, cycle.angle(key, i / cycle.n))) > 0.3) expect(body).toContain("1 * var(--sw-gap-w)");
          }
        }
      });
      it("paints overlapping flaps in depth order (the one nearer the viewer on top)", () => {
        for (let i = 0; i <= cycle.n; i++) {
          const at = Object.fromEntries(FLAP_KEYS.map(key => [key, cycle.angle(key, i / cycle.n)])) as Record<FlapKey, number>;
          const order = (key: FlapKey) => FLAP_SLOTS.findIndex(s => s.key === key && (s.layer === undefined || s.layer === flapLayer(at[key])));
          for (let a = 0; a < 4; a++) for (let b = a + 1; b < 4; b++) {
            const [p, q] = [FLAP_KEYS[a], FLAP_KEYS[b]];
            if (at[p] >= 150 && at[q] >= 150) continue; // both lying on the lid: the closing order decides
            const [front, back] = order(p) > order(q) ? [p, q] : [q, p];
            const [pf, pb] = [polygon(front, at[front]), polygon(back, at[back])];
            let right = 0, wrong = 0;
            for (let x = -12; x <= 148; x += 1.5) for (let y = -30; y <= 126; y += 1.5) {
              if (!inside(pf, [x, y]) || !inside(pb, [x, y])) continue;
              if (depth(pf, at[front], [x, y]) >= depth(pb, at[back], [x, y]) - 0.05) right++; else wrong++;
            }
            expect(wrong, `${mode} frame ${i}: ${back} is nearer than ${front} but painted under it`).toBeLessThanOrEqual(Math.max(2, 0.05 * (right + wrong)));
          }
        }
      });
      it("shows tr in exactly one layer on every frame, and the layer it should be in", () => {
        for (let i = 0; i <= cycle.n; i++) {
          const layer = flapLayer(cycle.angle("tr", i / cycle.n));
          expect(keyframeAt(`${cycle.name}-tr-z0`, i, cycle.n)).toBe(`opacity:${layer === 0 ? 1 : 0}`);
          expect(keyframeAt(`${cycle.name}-tr-z1`, i, cycle.n)).toBe(`opacity:${layer === 1 ? 1 : 0}`);
        }
      });
      it("is the resting logo on its resting frames: no transform, logo colour, no outline, no cap", () => {
        const rest = mode === "loop" ? [Math.round(0.5 * cycle.n)] : mode === "hov" ? [0, cycle.n] : [cycle.n];
        for (const i of rest) {
          expect(angles(i).every(deg => deg === 0)).toBe(true);
          for (const key of FLAP_KEYS) expect(keyframeAt(`${cycle.name}-${key}`, i, cycle.n)).toBe("transform:none;fill:var(--c);stroke-width:0");
          expect(keyframeAt(`${cycle.name}-p`, i, cycle.n)).toBe("opacity:0");
          expect(keyframeAt(`${cycle.name}-tr-z1`, i, cycle.n)).toBe("opacity:0");
          expect(keyframeAt(`${cycle.name}-w`, i, cycle.n)).toBe("opacity:0");
        }
      });
      it("is the solid shut box with four flap regions on its shut frames", () => {
        const shut = mode === "once" ? 0 : mode === "loop" ? Math.round(0.9 * cycle.n) : Math.round(fold * cycle.n) + 1;
        expect(angles(shut).every(deg => deg === 180)).toBe(true);
        const at = Object.fromEntries(FLAP_KEYS.map(key => [key, cycle.angle(key, shut / cycle.n)])) as Record<FlapKey, number>;
        const seen = new Set(RIM_POINTS.map(point => topmost(at, point)));
        expect([...seen].sort()).toEqual(["bl", "br", "tl", "tr"]);
        for (const [point, key] of [[[67, 30], "tl"], [[91, 47], "tr"], [[44, 47], "bl"], [[67, 64], "br"]] as [Pt, FlapKey][]) {
          expect(topmost(at, point), `${mode} lid position ${point}`).toBe(key);
        }
        expect(keyframeAt(`${cycle.name}-p`, shut, cycle.n)).toBe("opacity:1");
        expect(keyframeAt(`${cycle.name}-tr-z1`, shut, cycle.n)).toBe("opacity:1");
        expect(keyframeAt(`${cycle.name}-tr`, shut, cycle.n)).toContain("fill:var(--c)");
      });
    });
  }

  for (const theme of ["light", "dark"] as const) for (const variant of ["theme", "g-light", "g-dark", "mono", "forced-colors"] as const) {
    for (const [mode, cycle] of Object.entries(CYCLES)) it(`${theme} ${variant} ${mode}: four shut regions, own colours, no body holes at any sample`, () => {
      const art = variant === "mono" || variant === "g-dark" ? "dark" : variant === "g-light" ? "light" : theme;
      const themeSvg = boxOpenSvg().split("</svg>")[art === "light" ? 0 : 1];
      const cap = themeSvg.slice(themeSvg.indexOf('<g class="p">'), themeSvg.indexOf('</g>'));
      for (let i = 0; i <= cycle.n; i++) {
        const at = Object.fromEntries(FLAP_KEYS.map(key => [key, cycle.angle(key, i / cycle.n)])) as Record<FlapKey, number>;
        const live = moving(Object.values(at));
        // Both themes' body faces are always covered: dark's cut-away master gets the full-height cap
        // on every moving frame, not just near shut. Its resting cut-outs are covered by the static flaps.
        if (art === "dark" && live) {
          expect(keyframeAt(`${cycle.name}-p`, i, cycle.n)).toBe("opacity:1");
          for (const face of logoMasters.symbol.paths.slice(0, 2)) expect(cap).toContain(face.d);
        }
        for (const key of FLAP_KEYS) expect(keyframeAt(`${cycle.name}-${key}`, i, cycle.n)).toContain("fill:var(--c)");
        if (Object.values(at).every(deg => deg === 180)) {
          const seen = new Set(RIM_POINTS.map(point => topmost(at, point)));
          expect([...seen].sort()).toEqual(["bl", "br", "tl", "tr"]); // undefined would be a hole
        }
      }
      if (variant === "mono") {
        expect(boxMonoCss()).toContain("--sw-ramp-w:3.8px");
        expect(boxMonoCss()).toContain(".sw-box.mono .f{fill:currentColor;");
      }
      if (variant === "forced-colors") expect(css).toContain("fill:CanvasText!important");
      if (variant === "g-light" || variant === "g-dark") expect(boxGroundCss()).toContain(`.sw-box.${variant}`);
    });
  }

  it("draws the masters' paths for the flaps, so the resting frame is the static logo", () => {
    const svg = boxOpenSvg();
    for (const master of ["symbol", "symbol-reversed"] as const) {
      for (const path of logoMasters[master].paths.slice(-4)) expect(svg).toContain(`d="${path.d}"`);
    }
  });
});
