// Drawing helpers for the on-screen card: fitted text, the barcode and photo filters.
// The server PDF is the authority; these keep the designer and "My cards" faithful to it.
import { useId, useMemo, type CSSProperties, type ReactNode } from "react";

import type { Layer } from "./cardTypes";
import { PT_TO_MM } from "./cardGeometry";
import { cssFamily } from "./fontLoader";
import { canvasMeasure, fitText } from "./textFit";

/** Font size (CSS px) and wrapping for a text layer, matching the renderer's shrink-to-fit. */
export function useFittedText(layer: Layer, text: string, px: number): CSSProperties {
  const family = layer.font_family ?? "Gilroy";
  const weight = layer.font_weight ?? 400;
  const style = useMemo(() => ({ family: `SW Card ${family}`, weight, sizePt: layer.font_size_pt ?? 10,
    lineHeight: layer.line_height ?? 1.2, trackingPt: layer.tracking_pt ?? 0, uppercase: layer.uppercase,
    shrink: layer.shrink_to_fit !== false }), [family, weight, layer.font_size_pt, layer.line_height, layer.tracking_pt,
    layer.uppercase, layer.shrink_to_fit]);
  const fitted = useMemo(() => fitText(text, style, layer.w_mm / PT_TO_MM, layer.h_mm / PT_TO_MM, canvasMeasure(style)),
    [text, style, layer.w_mm, layer.h_mm]);
  return { fontFamily: `${cssFamily(family)}, ${family}, sans-serif`, fontWeight: weight,
    fontSize: fitted.sizePt * PT_TO_MM * px, whiteSpace: fitted.oneLine ? "nowrap" : undefined };
}

/** Deterministic stand-in bars for the designer (the real code is drawn by the server). */
function placeholderBars() {
  const bars: { x: number; w: number }[] = [];
  let x = 10, seed = 7;
  while (x < 110) {
    seed = (seed * 37 + 11) % 97;
    const w = 1 + (seed % 3);
    bars.push({ x, w });
    x += w + 1 + ((seed >> 2) % 3);
  }
  return bars;
}
const BARS = placeholderBars();

export function BarcodeView({ layer, values, image }: { layer: Layer; values: Record<string, string>; image?: string | null }) {
  const label = layer.source === "desk" ? "DESK CODE" : values.number ?? "";
  const showText = layer.show_text !== false;
  return <div className="flex h-full w-full flex-col bg-white" aria-hidden="true">
    <div className="min-h-0 flex-1">
      {image ? <img src={image} alt="" className="h-full w-full" style={{ objectFit: "fill", imageRendering: "pixelated" }} />
        : <svg viewBox="0 0 120 40" preserveAspectRatio="none" className="h-full w-full" shapeRendering="crispEdges">
          {BARS.map((bar) => <rect key={bar.x} x={bar.x} y="2" width={bar.w} height="36" fill="#000000" />)}
        </svg>}
    </div>
    {showText ? <div className="truncate text-center font-medium leading-none text-black"
      style={{ fontSize: "clamp(4px, 22%, 12px)", letterSpacing: "0.08em" }}>{label}</div> : null}
  </div>;
}

/** A CSS filter (and the SVG filter it points at, for duotone) for a photo layer. */
export function usePhotoFilter(layer: Layer, mono: boolean): { filter?: string; defs: ReactNode } {
  const id = `duo-${useId().replace(/[^a-zA-Z0-9-]/g, "")}`;
  if (mono || layer.filter === "grey") return { filter: "grayscale(1) contrast(1.05)", defs: null };
  if (layer.filter !== "duotone") return { defs: null };
  const channel = (hex: string, offset: number) => parseInt((hex || "#000000").slice(offset, offset + 2), 16) / 255;
  const dark = layer.duotone_dark ?? "#142C2A", light = layer.duotone_light ?? "#DFFF8F";
  const table = (offset: number) => `${channel(dark, offset)} ${channel(light, offset)}`;
  return { filter: `url(#${id})`, defs: <svg width="0" height="0" className="absolute" aria-hidden="true" focusable="false">
    <filter id={id} colorInterpolationFilters="sRGB">
      <feColorMatrix type="matrix" values="0.2126 0.7152 0.0722 0 0 0.2126 0.7152 0.0722 0 0 0.2126 0.7152 0.0722 0 0 0 0 0 1 0" />
      <feComponentTransfer>
        <feFuncR type="table" tableValues={table(1)} />
        <feFuncG type="table" tableValues={table(3)} />
        <feFuncB type="table" tableValues={table(5)} />
      </feComponentTransfer>
    </filter>
  </svg> };
}
