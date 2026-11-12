// A barcode layer on screen. The designer draws the SERVER's encoding of the previewed value (barcodes.ts), with the
// same rectangles as print; a holder's own card uses the server's SVG of their real code. While the encoding loads,
// or with no design to ask, a neutral stand-in is shown.
import type { Layer } from "./cardTypes";
import { BARCODE_TEXT_MM, barcodeRects, isMatrixCode, previewValue, symbologyOf, useBarcodeEncoding } from "./barcodes";

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

export function BarcodeView({ layer, values, image, designId = 0 }: { layer: Layer; values: Record<string, string>;
  image?: string | null; designId?: number }) {
  const symbology = symbologyOf(layer);
  const matrix = isMatrixCode(symbology);
  const encoding = useBarcodeEncoding(designId, symbology, previewValue(layer, values), !image);
  const showText = layer.show_text !== false && !matrix;
  const text = encoding.data?.kind === "linear" ? encoding.data.text : values.number ?? "";
  const label = layer.source === "desk" ? "DESK CODE" : text;
  const textMm = showText ? BARCODE_TEXT_MM : 0;
  if (encoding.data && !image) {
    const { w_mm: w, h_mm: h } = layer;
    return <svg viewBox={`0 0 ${w} ${h}`} className="block h-full w-full bg-white" aria-hidden="true" shapeRendering="crispEdges">
      <rect width={w} height={h} fill="#FFFFFF" />
      {barcodeRects(encoding.data, w, h, textMm).map(([x, y, rw, rh], index) => <rect key={index} x={x} y={y} width={rw} height={rh} fill="#000000" />)}
      {showText ? <text x={w / 2} y={h - textMm / 2} fontSize={(6 * 25.4) / 72} textAnchor="middle" dominantBaseline="central"
        fontFamily="Outfit, sans-serif" fontWeight={500} letterSpacing={0.6 * 25.4 / 72} fill="#000000">{label}</text> : null}
    </svg>;
  }
  return <div className="flex h-full w-full flex-col bg-white" aria-hidden="true">
    <div className="min-h-0 flex-1">
      {image ? <img src={image} alt="" className="h-full w-full" style={{ objectFit: matrix ? "contain" : "fill", imageRendering: "pixelated" }} />
        : <svg viewBox="0 0 120 40" preserveAspectRatio="none" className="h-full w-full" shapeRendering="crispEdges">
          {BARS.map((bar) => <rect key={bar.x} x={bar.x} y="2" width={bar.w} height="36" fill="#000000" />)}
        </svg>}
    </div>
    {showText ? <div className="truncate text-center font-medium leading-none text-black"
      style={{ fontSize: "clamp(4px, 22%, 12px)", letterSpacing: "0.08em" }}>{label}</div> : null}
  </div>;
}
