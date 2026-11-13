import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Background, GradientSpec, Layer, Side } from "./cardTypes";
import { backgroundStyle, CardLayerView } from "./CardLayerView";
import { SideBackground } from "./SideBackground";
import { cssNumber, gradientCss, rgbCss } from "./studioMath";

// SECURITY-REVIEW L-F2: a stored document that skipped the server's #RRGGBB and range checks must
// never inject a url() (a third-party beacon) or extra gradient arguments into CSS.
const BEACON = "red 0%), url(https://beacon.example/?b), linear-gradient(red";

describe("Card Studio CSS never interpolates raw document text", () => {
  it("turns colours into rgb() and refuses anything that is not #RRGGBB", () => {
    expect(rgbCss("#FF7447")).toBe("rgb(255, 116, 71)");
    expect(rgbCss("#006e63")).toBe("rgb(0, 110, 99)");
    for (const bad of [BEACON, "url(https://x)", "red", "#FFF", null, undefined, 7]) expect(rgbCss(bad)).toBe("rgb(0, 0, 0)");
  });

  it("coerces numbers with Number() and clamps, falling back on non-numbers", () => {
    expect(cssNumber(45, 0, 0, 360)).toBe(45);
    expect(cssNumber("90", 0, 0, 360)).toBe(90);
    expect(cssNumber(999, 0, 0, 360)).toBe(360);
    for (const bad of ["0deg, url(https://x)", NaN, Infinity, null, undefined, {}]) expect(cssNumber(bad, 50, 0, 100)).toBe(50);
  });

  it("keeps a normal gradient and neutralises a hostile one", () => {
    const linear: GradientSpec = { type: "linear", angle_deg: 90, stops: [{ colour: "#FF0000", at: 0 }, { colour: "#0000FF", at: 100 }] };
    expect(gradientCss(linear, 85.6, 54)).toBe("linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)");
    const hostile = { type: "radial", angle_deg: "0deg, url(https://beacon.example/a)", cx_pct: "50%, url(https://beacon.example/c)",
      cy_pct: "1) url(x", radius_pct: "1e999", stops: [{ colour: BEACON, at: "0" }, { colour: "#FFFFFF", at: 100 }] } as unknown as GradientSpec;
    for (const css of [gradientCss(hostile, 85.6, 54), gradientCss(hostile, 85.6, 54, true), gradientCss({ ...hostile, type: "linear" }, 85.6, 54)]) {
      expect(css).not.toMatch(/url\(|beacon/);
    }
    expect(gradientCss(hostile, 85.6, 54)).toContain("at 50% 50%");
  });

  it("neutralises hostile colours in the layer and side background styles", () => {
    const style = backgroundStyle({ kind: "colour", colour: `#000000; ${BEACON}` } as unknown as Background, null);
    expect(String(style.background)).toBe("rgb(0, 0, 0)");
    const image = backgroundStyle({ kind: "image", fallback: BEACON, dim_pct: "1), url(https://x)", fit: "cover" } as unknown as Background, null);
    expect(JSON.stringify(image)).not.toMatch(/url\(|beacon/);

    const side = { page_width_mm: 85.6, page_height_mm: 54, overlay: null,
      background: { kind: "colour", colour: BEACON } } as unknown as Side;
    const { container } = render(<SideBackground side={side} mono={false} imageUrl={null} px={4} />);
    expect(container.innerHTML).not.toMatch(/url\(|beacon/);
    expect(container.innerHTML).toContain("rgb(0, 0, 0)");
  });

  it("paints a normal shape fill and stroke, and neutralises hostile ones", () => {
    const shape = (fill: unknown, stroke: unknown) => ({ id: "s", kind: "shape", shape: "rect", x_mm: 0, y_mm: 0, width_mm: 10,
      height_mm: 10, rotation: 0, opacity: 1, fill, stroke, stroke_mm: 0.3 }) as unknown as Layer;
    const draw = (layer: Layer) => render(<CardLayerView layer={layer} px={4} values={{}} designId={1} mono={false} />).container;
    const normal = draw(shape("#006E63", "#FF7447"));
    expect(normal.innerHTML).toContain("rgb(0, 110, 99)");
    expect(normal.innerHTML).toContain("rgb(255, 116, 71)");
    expect(draw(shape(BEACON, `#000000 url(https://beacon.example/s)`)).innerHTML).not.toMatch(/url\(|beacon/);
  });
});
