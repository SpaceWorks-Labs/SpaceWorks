// The design's watermark on screen, drawn under every layer exactly as the renderer does
// (apps/card_designs/rendering_background.draw_watermark): text in Gilroy Bold, centred and
// turned by its angle, sized from the card; an image contained in the middle 70 %.
import type { Watermark } from "./cardTypes";
import { PT_TO_MM } from "./cardGeometry";
import { useAssetUrl } from "./CardLayerView";
import { cssFamily } from "./fontLoader";

function monoColour(hex: string) {
  const [r, g, b] = [1, 3, 5].map((offset) => {
    const c = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.4 ? "#000000" : "#FFFFFF";
}

export function WatermarkView({ watermark, widthMm, heightMm, px, mono, designId, imageUrl }: {
  watermark: Watermark | undefined; widthMm: number; heightMm: number; px: number; mono: boolean; designId: number;
  /** A ready URL (the holder's own card); otherwise the designer fetches the asset itself. */
  imageUrl?: string | null;
}) {
  const fetched = useAssetUrl(designId, imageUrl === undefined && watermark?.kind === "image" ? watermark.asset_id : null);
  if (!watermark || watermark.kind === "none") return null;
  const opacity = watermark.opacity_pct / 100;
  if (watermark.kind === "image") {
    const url = imageUrl ?? fetched;
    return url ? <img src={url} alt="" aria-hidden="true" className="pointer-events-none absolute object-contain"
      style={{ left: "15%", top: "15%", width: "70%", height: "70%", opacity, filter: mono ? "grayscale(1)" : undefined }} />
      : null;
  }
  if (!watermark.text.trim()) return null;
  const widthPt = widthMm / PT_TO_MM, heightPt = heightMm / PT_TO_MM;
  const sizePt = Math.min((widthPt / Math.max(4, watermark.text.length)) * 1.6, heightPt * 0.4);
  return <div aria-hidden="true" className="pointer-events-none absolute inset-0 grid place-items-center overflow-hidden">
    <span className="whitespace-nowrap" style={{ fontFamily: `${cssFamily("Gilroy")}, Gilroy, sans-serif`, fontWeight: 700,
      fontSize: sizePt * PT_TO_MM * px, lineHeight: 1, opacity, color: mono ? monoColour(watermark.colour) : watermark.colour,
      transform: `rotate(${watermark.angle_deg}deg)` }}>{watermark.text}</span>
  </div>;
}
