// LOCAL test (never committed): text fit, device drafts, watermark view, face descriptions.
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CardDocument, Layer } from "./cardTypes";
import { clearDeviceDraft, readDeviceDraft, writeDeviceDraft } from "./deviceDraft";
import { fieldsFor } from "./dataFields";
import { fitText, wrap } from "./textFit";
import { WatermarkView } from "./WatermarkView";
import { describeFace, faceAspect, type CardFace } from "../../features/members/wallet/CardFaces";

const measure = (text: string, size: number) => text.length * size * 0.55;
const style = { family: "Gilroy", weight: 700, sizePt: 11, lineHeight: 1.15, trackingPt: 0, shrink: true };

describe("textFit", () => {
  it("keeps a name on one line down to 60 % before wrapping", () => {
    const fitted = fitText("Alexandra Montgomery", style, 100, 14, measure);
    expect(fitted.oneLine).toBe(true);
    expect(fitted.sizePt).toBeGreaterThanOrEqual(6.6);
    expect(fitted.sizePt).toBeLessThan(11);
  });
  it("wraps at full size when two lines fit", () => {
    expect(fitText("Alexandra Montgomery", style, 100, 30, measure)).toEqual({ sizePt: 11, oneLine: false });
  });
  it("falls back to wrapping when even 60 % is too wide", () => {
    const fitted = fitText("Alexandra Montgomery-Fitzgerald Junior", style, 60, 30, measure);
    expect(fitted.oneLine).toBe(false);
  });
  it("breaks a long word by characters", () => {
    expect(wrap("abcdefghij", 10, 30, measure).length).toBeGreaterThan(1);
  });
  it("draws at the design size without a measurer", () => {
    expect(fitText("x", style, 10, 10, null)).toEqual({ sizePt: 11, oneLine: false });
  });
});

const doc = { version: 2, stock: "cr80-landscape", back_enabled: false, mono: false,
  watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: -30, colour: "#006E63" },
  front: { page_width_mm: 85.6, page_height_mm: 53.98, background: { kind: "colour", colour: "#FFFFFF" }, layers: [] },
  back: { page_width_mm: 85.6, page_height_mm: 53.98, background: { kind: "colour", colour: "#FFFFFF" }, layers: [] },
} as unknown as CardDocument;

describe("device drafts", () => {
  afterEach(() => clearDeviceDraft(7));
  it("round-trips only for the same revision", () => {
    expect(writeDeviceDraft(7, 3, doc)).toBe(true);
    expect(readDeviceDraft(7, 3)?.document.stock).toBe("cr80-landscape");
    expect(readDeviceDraft(7, 4)).toBeNull();
    clearDeviceDraft(7);
    expect(readDeviceDraft(7, 3)).toBeNull();
  });
  it("ignores garbage", () => {
    window.localStorage.setItem("sw:card-design-draft:7", "{nope");
    expect(readDeviceDraft(7, 3)).toBeNull();
  });
});

describe("WatermarkView", () => {
  it("draws text watermarks and nothing for none", () => {
    const { container, rerender } = render(<WatermarkView watermark={{ ...doc.watermark, kind: "text", text: "COPY" }}
      widthMm={85.6} heightMm={53.98} px={5} mono={false} designId={1} imageUrl={null} />);
    expect(screen.getByText("COPY")).toBeInTheDocument();
    rerender(<WatermarkView watermark={doc.watermark} widthMm={85.6} heightMm={53.98} px={5} mono={false} designId={1}
      imageUrl={null} />);
    expect(container.textContent).toBe("");
  });
});

describe("answer fields", () => {
  it("adds programme answers after the built-in fields", () => {
    const fields = fieldsFor([{ key: "field:team", label: "Team" }]);
    expect(fields.at(-1)).toEqual({ key: "field:team", label: "Answer: Team" });
  });
});

describe("describeFace", () => {
  it("reads the card's text and names its codes", () => {
    const layer = (extra: Partial<Layer>) => ({ id: String(Math.random()), name: "", x_mm: 0, y_mm: 0, w_mm: 10, h_mm: 5,
      rotation: 0, opacity: 100, locked: false, hidden: false, ...extra }) as Layer;
    const face = { document: { ...doc, front: { ...doc.front, layers: [
      layer({ kind: "data_field", field: "name", text: "{{name}}" }), layer({ kind: "verify_qr", w_mm: 18, h_mm: 18 }),
      layer({ kind: "barcode" }), layer({ kind: "text", text: "Hidden", hidden: true })] } },
    values: { name: "Priya Raman" }, photo: null, logos: {}, assets: {}, desk_qr: null, verify_qr: null } as CardFace;
    const text = describeFace(face, "front");
    expect(text).toContain("Priya Raman");
    expect(text).toContain("public check page");
    expect(text).toContain("a barcode");
    expect(text).not.toContain("Hidden");
    expect(faceAspect({ ...face, document: { ...doc, front: { ...doc.front, page_width_mm: 53.98, page_height_mm: 85.6 } } }))
      .toBe("53.98 / 85.6");
  });
});
