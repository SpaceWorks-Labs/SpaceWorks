import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { logoMasters } from "../spaceWorksLogoPaths";
import { boxOpenCss } from "./css";
import { flapTransform, openAngle, loopAngle, FLAP_KEYS } from "./geometry";
import { boxOpenSvg } from "./markup";

const INDEX = resolve(process.cwd(), "index.html");
const between = (text: string, start: string, end: string) => {
  const from = text.indexOf(start) + start.length;
  return { from, to: text.indexOf(end), text: text.slice(from, text.indexOf(end)) };
};
const generated = { css: `\n${boxOpenCss("once")}\n`, svg: boxOpenSvg() };

// `UPDATE_SPLASH=1 npx vitest run src/components/boxOpen` rewrites the generated region of index.html.
if (process.env.UPDATE_SPLASH) {
  const html = readFileSync(INDEX, "utf8");
  const nl = html.includes("\r\n") ? "\r\n" : "\n";
  let next = html.replace(/\r\n/g, "\n");
  for (const [kind, start, end, value] of [["css", "/* sw-box:css:start */", "/* sw-box:css:end */", generated.css], ["svg", "<!-- sw-box:svg:start -->", "<!-- sw-box:svg:end -->", generated.svg]] as const) {
    void kind;
    const span = between(next, start, end);
    next = next.slice(0, span.from) + value + next.slice(span.to);
  }
  writeFileSync(INDEX, next.replace(/\n/g, nl));
}
// `SW_BOX_HARNESS=<file>` writes a page that shows the animation frozen at 0..100% (for the frame strip).
if (process.env.SW_BOX_HARNESS) {
  const steps = [0, 5, 10, 15, 20, 30, 45, 60, 75, 90, 100];
  const cells = steps.map(step => `<div class="cell"><div class="sw-box once" style="--p:${step}">${boxOpenSvg()}</div><b>${step}%</b></div>`).join("");
  writeFileSync(process.env.SW_BOX_HARNESS, `<!doctype html><meta charset="utf-8"><style>${boxOpenCss("once")}
body{margin:0;width:1200px;background:var(--bg,#FFF4E8);display:flex;flex-wrap:wrap;font:14px sans-serif;color:#142C2A}html.dark body{background:#000;color:#FFF4E8}
.cell{width:300px;height:280px;display:grid;place-items:center;position:relative}.cell b{position:absolute;bottom:6px;right:10px}
.sw-box{width:204px;height:189px}.sw-box *{animation-play-state:paused!important;animation-delay:calc(var(--p) * -16ms)!important}</style><body>${cells}`);
}

describe("box opening animation", () => {
  const html = readFileSync(INDEX, "utf8").replace(/\r\n/g, "\n");
  it("index.html carries exactly the generated splash CSS and SVG", () => {
    expect(between(html, "/* sw-box:css:start */", "/* sw-box:css:end */").text).toBe(generated.css);
    expect(between(html, "<!-- sw-box:svg:start -->", "<!-- sw-box:svg:end -->").text).toBe(generated.svg);
  });
  it("draws the brand paths of both masters verbatim, so the last frame is the static logo", () => {
    for (const key of ["symbol", "symbol-reversed"] as const) for (const path of logoMasters[key].paths) expect(generated.svg).toContain(`d="${path.d}"`);
  });
  it("starts shut, ends exactly open (identity transforms) and overshoots in between", () => {
    for (const key of FLAP_KEYS) {
      expect(openAngle(key, 0)).toBe(180);
      expect(openAngle(key, 1)).toBe(0);
      expect(flapTransform(key, 0)).toBe("none");
      expect(Math.min(...Array.from({ length: 200 }, (_, i) => openAngle(key, i / 199)))).toBeLessThan(0);
      expect(loopAngle(key, 0.5)).toBe(0);
      expect(loopAngle(key, 0.95)).toBe(180);
    }
  });
  it("keeps every flap hinge fixed under the swing and folds the lid back over the opening", () => {
    const m = /matrix\(([^)]+)\)/.exec(flapTransform("tl", 90))!;
    const [a, b, c, d, e, f] = m[1].split(",").map(Number);
    const hinge = (x: number, y: number) => [a * x + c * y + e, b * x + d * y + f];
    expect(hinge(65.44, 15)[0]).toBeCloseTo(65.44, 1);
    expect(hinge(21.26, 46.5)[1]).toBeCloseTo(46.5, 1);
    const folded = /matrix\(([^)]+)\)/.exec(flapTransform("tr", 180))!;
    const [fa, fb, fc, fd, fe, ff] = folded[1].split(",").map(Number);
    // tr's outer tip lands on the hinge start minus the (slightly stretched) outward vector: over the box.
    expect(fa * 90.15 + fc * 0.6 + fe).toBeCloseTo(69.85 - 20.3 * 1.14, 0);
    expect(fb * 90.15 + fd * 0.6 + ff).toBeCloseTo(15 + 14.4 * 1.14 - 1.6, 0);
  });
  it("respects reduced motion: every animation is switched off for a still logo", () => {
    expect(boxOpenCss()).toContain("@media (prefers-reduced-motion:reduce)");
  });
});
