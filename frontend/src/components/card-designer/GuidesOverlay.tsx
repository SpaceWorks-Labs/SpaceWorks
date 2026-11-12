// Editor-only guides drawn over a side: the safe zone, the printer margin, the punch slot
// and custom rulers (the bleed band sits outside the trim, in CanvasFrame). Never printed. Decorative (aria-hidden); the same
// numbers live in the Guides panel.
import type { Guides, SideName } from "./cardTypes";
import { SAFE_AREA_MM } from "./cardGeometry";

export const DEFAULT_GUIDES: Guides = { bleed_mm: 0, safe_mm: SAFE_AREA_MM, margin_mm: 0, punch_slot: null, rulers: [] };
export const guidesOf = (guides?: Guides): Guides => ({ ...DEFAULT_GUIDES, ...guides });

export function GuidesOverlay({ guides, px, side }: {
  guides?: Guides; px: number; side: SideName;
}) {
  const g = guidesOf(guides);
  const slot = g.punch_slot && (g.punch_slot.side === "both" || g.punch_slot.side === side) ? g.punch_slot : null;
  return <div aria-hidden="true" className="pointer-events-none absolute inset-0">
    {g.safe_mm > 0 ? <div className="absolute border border-dashed border-accent-ink/50" style={{ inset: g.safe_mm * px }} /> : null}
    {g.margin_mm > 0 ? <div className="absolute border border-dashed" style={{ inset: g.margin_mm * px, borderColor: "#B45309" }} /> : null}
    {g.rulers.map((ruler, index) => <span key={index} className="absolute"
      style={{ background: "#7C3AED", ...(ruler.axis === "x" ? { left: ruler.at_mm * px, top: 0, bottom: 0, width: 1 }
        : { top: ruler.at_mm * px, left: 0, right: 0, height: 1 }) }} />)}
    {slot ? <div className="absolute border-2 border-dashed" style={{ left: slot.x_mm * px, top: slot.y_mm * px,
      width: slot.w_mm * px, height: slot.h_mm * px, borderColor: "#BE123C", background: "rgba(190,18,60,0.08)",
      borderRadius: slot.shape === "round" ? "50%" : slot.h_mm * px / 2 }} /> : null}
  </div>;
}

/** A punch slot centred horizontally near the top: a 12 x 3 mm pill or a 5 mm circle (spec section 1). */
export function newPunchSlot(shape: "slot" | "round", widthMm: number, side: "front" | "back" | "both" = "both") {
  const w = shape === "slot" ? 12 : 5, h = shape === "slot" ? 3 : 5;
  return { shape, x_mm: Math.round((widthMm - w) * 5) / 10, y_mm: 4, w_mm: w, h_mm: h, side };
}
