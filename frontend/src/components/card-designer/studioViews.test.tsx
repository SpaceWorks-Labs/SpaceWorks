import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Layer, Side } from "./cardTypes";
import { CardLayerView } from "./CardLayerView";
import { newLayer } from "./designDocument";
import { brandSwatches, setAccentColour, setBackgroundColour, setTextColour, turnedStock, turnPaper } from "./quickEdits";
import { SideBackground } from "./SideBackground";
import { applyStock } from "./designDocument";
import type { CardDocument } from "./cardTypes";

const side: Side = { page_width_mm: 54, page_height_mm: 86, background: { kind: "colour", colour: "#FFFFFF" }, layers: [] };
const layer = (kind: Parameters<typeof newLayer>[0], extra: Partial<Layer> = {}) => newLayer(kind, side, "cr80-portrait", extra);
const show = (value: Layer, values: Record<string, string> = { name: "Priya Raman" }) =>
  render(<div style={{ width: 200, height: 100 }}><CardLayerView layer={value} px={4} values={values} designId={1} mono={false} /></div>);

describe("studio layer views", () => {
  it("draws rich text as lines with one run per word and space, a highlight bar and a stroke", () => {
    const { container } = show(layer("text", { text: "Hi there", spans: [{ text: "Hi ", font_weight: 300 }, { text: "there", font_weight: 800 }],
      highlight: { colour: "#DFFF8F", pad_x_mm: 1, pad_y_mm: 0.5, radius_mm: 0.5 }, stroke: { colour: "#FFFFFF", width_pt: 1 }, w_mm: 40, h_mm: 10 }));
    expect(screen.getByRole("img", { name: "Hi there" })).toBeTruthy();
    expect(container.querySelectorAll("tspan").length).toBe(3);
    expect(container.querySelectorAll("rect").length).toBe(1);
    expect(container.querySelector("tspan")?.getAttribute("stroke")).toBe("#FFFFFF");
  });
  it("keeps plain text on the light HTML path", () => {
    const { container } = show(layer("text", { text: "Plain" }));
    expect(container.querySelector("svg")).toBeNull();
    expect(screen.getByText("Plain")).toBeTruthy();
  });
  it("draws a gradient arch as SVG with a gradient fill and a shadow", () => {
    const { container } = show(layer("shape", { shape: "arch", fill_gradient: { type: "linear", angle_deg: 90, stops: [{ colour: "#000000", at: 0 }, { colour: "#FFFFFF", at: 100 }] },
      shadow: { dx_mm: 1, dy_mm: 1, blur_mm: 2, colour: "#000000", opacity_pct: 40 } }));
    expect(container.querySelector("linearGradient")).not.toBeNull();
    expect(container.querySelector("path")?.getAttribute("fill")).toMatch(/^url\(#/);
    expect(container.querySelector("svg")?.getAttribute("style")).toContain("drop-shadow");
  });
  it("draws a cut-out photo as an unmasked silhouette with a sticker outline filter, even with no photo yet", () => {
    const { container } = show(layer("photo", { variant: "cutout", outline: { width_mm: 1.2, colour: "#FFFFFF" } }));
    expect(container.querySelector("filter feGaussianBlur")).not.toBeNull();
    expect(container.querySelector("ellipse")).not.toBeNull();
  });
  it("skips absent signatories and spaces the rest equally", () => {
    const values = { signatory_1_name: "A", signatory_2_name: "", signatory_3_name: "C" };
    show(layer("signature_row", { slots: [1, 2, 3], w_mm: 120, h_mm: 24, gap_mm: 10 }), values);
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getByText("C")).toBeTruthy();
    expect(screen.queryByText("B")).toBeNull();
  });
  it("prints the short serial upper-cased", () => {
    show(layer("certificate_id", { format: "short" }), { serial: "abcdef12-0000" });
    expect(screen.getByText("ABCDEF12")).toBeTruthy();
  });
  it("draws a seal with its label and ring text", () => {
    const { container } = show(layer("seal", { label: "SW", ring_text: "TINKERSPACE", style: "star" }));
    expect(container.querySelector("textPath")?.textContent).toBe("TINKERSPACE");
    expect(screen.getByText("SW")).toBeTruthy();
  });
  it("layers an overlay gradient with alpha over a blurred, darkened image background", () => {
    const { container } = render(<div style={{ width: 200, height: 100 }}><SideBackground px={4} mono={false} imageUrl="blob:x" side={{ ...side,
      background: { kind: "image", asset_id: "a", fit: "cover", dim_pct: 30, blur_mm: 2, zoom: 2, focal_x_pct: 20, focal_y_pct: 80 },
      overlay: { type: "linear", angle_deg: 180, stops: [{ colour: "#000000", at: 0, alpha_pct: 0 }, { colour: "#000000", at: 100, alpha_pct: 80 }] } }} /></div>);
    const img = container.querySelector("img")!;
    expect(img.style.filter).toContain("blur(8px)");
    expect(img.style.objectPosition).toBe("20% 80%");
    expect(img.style.transform).toBe("scale(2)");
    expect(container.innerHTML).toContain("rgba(0, 0, 0, 0.8)");
  });
});

describe("quick edits", () => {
  const document: CardDocument = { version: 2, stock: "cr80-portrait", back_enabled: false, mono: false,
    watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: -30, colour: "#000000" },
    front: { ...side, layers: [layer("text"), layer("band"), layer("photo")] }, back: side };
  it("recolours the background, the text and the accents", () => {
    expect(setBackgroundColour(document, "front", "#142C2A").front.background).toEqual({ kind: "colour", colour: "#142C2A" });
    expect(setTextColour(document, "front", "#FFFFFF").front.layers[0].colour).toBe("#FFFFFF");
    expect(setAccentColour(document, "front", "#FF7447").front.layers[1].fill).toBe("#FF7447");
  });
  it("turns the paper the other way and scales layers to fit", () => {
    expect(turnedStock("cr80-portrait")).toBe("cr80-landscape");
    expect(turnedStock("3x4")).toBe("4x3");
    expect(turnedStock("badge-90x130")).toBe("badge-130x90");
    const turned = turnPaper(document);
    expect(turned.stock).toBe("cr80-landscape");
    expect(turned.front.page_width_mm).toBeGreaterThan(turned.front.page_height_mm);
    expect(applyStock(document, "a4-landscape").front.page_width_mm).toBeCloseTo(297);
    expect(brandSwatches()).toHaveLength(8);
  });
});
