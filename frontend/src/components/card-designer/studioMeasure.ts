// Text measurement for the studio's rich-text layout. A canvas measures the real, loaded face (widths in points,
// 1 CSS px treated as 1 pt, without letter-spacing: the plan adds that per character like the server). With no
// canvas (tests) a fixed average advance stands in so layout stays deterministic.
import { useEffect, useState } from "react";

import { canonicalFamily } from "./fontLoader";
import type { MeasureText } from "./studioText";

let context: CanvasRenderingContext2D | null | undefined;
function canvas(): CanvasRenderingContext2D | null {
  if (context === undefined) {
    try { context = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null; } catch { context = null; }
  }
  return context;
}

/** Average-advance fallback: 0.55 em per character. */
export const fallbackMeasure: MeasureText = (text, _span, sizePt) => [...text].length * 0.55 * sizePt;

export const canvasMeasure: MeasureText = (text, span, sizePt) => {
  const ctx = canvas();
  if (!ctx || !text) return text ? fallbackMeasure(text, span, sizePt) : 0;
  const family = canonicalFamily(span.family);
  ctx.font = `${span.weight} ${sizePt}px "SW Card ${family}", "${family}", sans-serif`;
  const width = ctx.measureText(text).width;
  // A canvas without a real text engine (jsdom's stub) reports 0: fall back so layout stays usable.
  return width > 0 ? width : fallbackMeasure(text, span, sizePt);
};

/** A counter that changes when a font finishes loading, so layouts measured with a fallback face re-run. */
export function useFontEpoch() {
  const [epoch, setEpoch] = useState(0);
  useEffect(() => {
    const fonts = typeof document !== "undefined" ? document.fonts : undefined;
    if (!fonts?.addEventListener) return;
    const bump = () => setEpoch((value) => value + 1);
    fonts.addEventListener("loadingdone", bump);
    return () => fonts.removeEventListener("loadingdone", bump);
  }, []);
  return epoch;
}
