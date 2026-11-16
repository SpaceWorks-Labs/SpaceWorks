import { describe, expect, it } from "vitest";

import { safeSvg } from "../../../../events/hackathonSubmissions/AssetPreview";
import { dxfToSvg, gcodeToSvg } from "./drawings";
import { extensionOf, previewKind } from "./previewKinds";
import { sanitizeSvg } from "./svgFile";

const paths = (svg: string) => [...svg.matchAll(/<path d="([^"]+)"/g)].map(match => match[1]);

describe("previewKind", () => {
  it("previews the decision's safe formats only", () => {
    expect(["part.STL", "a.3mf", "plate.gcode.3mf", "cut.gcode", "mill.nc", "sheet.dxf", "logo.svg"].map(name => previewKind(extensionOf(name))))
      .toEqual(["mesh", "mesh", "mesh", "toolpath", "toolpath", "drawing", "image"]);
    expect(previewKind(extensionOf("board.kicad_pcb"))).toBeNull();
    expect(previewKind(extensionOf("notes.pdf"))).toBeNull();
    expect(previewKind(extensionOf("README"))).toBeNull();
  });
});

describe("gcodeToSvg", () => {
  it("draws extruding moves only and passes the strict SVG check", () => {
    const svg = gcodeToSvg(["G21", "G90", "M82", "G0 X0 Y0", "G1 X10 Y0 E1", "G1 X10 Y10 E2", "G0 X50 Y50",
      "G1 X60 Y50 E3 ; perimeter", "G1 X70 Y50 E3"].join("\n"), "rgb(1,2,3)");
    expect(paths(svg)).toEqual(["M0 0 L10 0 L10 10", "M50 50 L60 50"]);
    expect(svg).toContain('stroke="rgb(1,2,3)"');
    expect(() => safeSvg(svg)).not.toThrow();
  });

  it("draws every feed move of a laser or CNC file (no extrusion), in inches and relative mode", () => {
    const svg = gcodeToSvg(["G20", "G91", "G0 X1", "G1 Y1 F300", "G1 X1"].join("\n"), "black");
    expect(paths(svg)).toEqual(["M25.4 0 L25.4 25.4 L50.8 25.4"]);
  });

  it("refuses a file with nothing to draw", () => {
    expect(() => gcodeToSvg("M104 S200\nG28\n", "black")).toThrow();
  });
});

describe("dxfToSvg", () => {
  const dxf = (...entities: string[]) => ["0", "SECTION", "2", "ENTITIES", ...entities, "0", "ENDSEC", "0", "EOF"].join("\n");

  it("reads lines, closed polylines, circles and arcs", () => {
    const svg = dxfToSvg(dxf(
      "0", "LINE", "8", "0", "10", "0", "20", "0", "11", "100", "21", "0",
      "0", "LWPOLYLINE", "70", "1", "10", "0", "20", "0", "10", "10", "20", "0", "10", "10", "20", "10",
      "0", "CIRCLE", "10", "50", "20", "50", "40", "5",
      "0", "ARC", "10", "0", "20", "0", "40", "10", "50", "0", "51", "90",
    ), "black");
    const drawn = paths(svg);
    expect(drawn[0]).toBe("M0 0 L100 0");
    expect(drawn[1]).toBe("M0 0 L10 0 L10 10 L0 0");
    expect(drawn[2].startsWith("M10 0 L")).toBe(true);
    expect(svg).toContain('<circle cx="50" cy="50" r="5"/>');
    expect(() => safeSvg(svg)).not.toThrow();
  });

  it("refuses binary DXF and a file without an entities section", () => {
    expect(() => dxfToSvg("AutoCAD Binary DXF\r\n\x1a\x00", "black")).toThrow();
    expect(() => dxfToSvg(["0", "SECTION", "2", "HEADER", "0", "ENDSEC", "0", "EOF"].join("\n"), "black")).toThrow();
  });
});

describe("sanitizeSvg", () => {
  it("strips scripts, handlers, foreign content and outside references but keeps the drawing", () => {
    const clean = sanitizeSvg(`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
      <script>alert(1)</script><foreignObject><div>x</div></foreignObject>
      <rect width="10" height="10" onclick="alert(1)" style="fill:url(https://evil.test/a.svg)"/>
      <image xlink:href="https://evil.test/p.png"/><use href="#r"/><text x="1" y="2">Logo</text></svg>`);
    expect(clean).not.toMatch(/script|foreignObject|onclick|evil\.test/);
    expect(clean).toContain("<text");
    expect(clean).toContain('href="#r"');
  });

  it("refuses DTDs and anything that is not an SVG", () => {
    expect(() => sanitizeSvg('<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>')).toThrow();
    expect(() => sanitizeSvg("<html></html>")).toThrow();
  });
});
