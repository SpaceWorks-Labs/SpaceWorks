// SVG pieces shared by the shape, photo-outline and seal views: gradients, the sticker-outline filter and the arch path.
import { useId, type ReactNode } from "react";

import type { GradientSpec, Outline, Shadow } from "./cardTypes";
import { PX_PER_MM, rgbaCss, sortedStops } from "./studioMath";

/** An SVG paint server for `spec` in a w x h mm box (CSS gradient-line rule for the angle). Returns [id, element]. */
export function useGradientDef(spec: GradientSpec | null | undefined, w: number, h: number): [string | null, ReactNode] {
  const id = `g${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  if (!spec) return [null, null];
  const stops = sortedStops(spec.stops).map((stop, index) => <stop key={index} offset={`${stop.at}%`}
    stopColor={stop.colour} stopOpacity={(stop.alpha_pct ?? 100) / 100} />);
  if (spec.type === "radial") {
    const radius = (spec.radius_pct ?? 100) / 100 * Math.hypot(w, h) / 2;
    return [id, <radialGradient key={id} id={id} gradientUnits="userSpaceOnUse" cx={w * (spec.cx_pct ?? 50) / 100}
      cy={h * (spec.cy_pct ?? 50) / 100} r={Math.max(0.01, radius)}>{stops}</radialGradient>];
  }
  const angle = (spec.angle_deg * Math.PI) / 180;
  const length = Math.abs(w * Math.sin(angle)) + Math.abs(h * Math.cos(angle));
  const dx = Math.sin(angle) * length / 2, dy = -Math.cos(angle) * length / 2;
  return [id, <linearGradient key={id} id={id} gradientUnits="userSpaceOnUse" x1={w / 2 - dx} y1={h / 2 - dy}
    x2={w / 2 + dx} y2={h / 2 + dy}>{stops}</linearGradient>];
}

/** The server's sticker outline as an SVG filter: blur the alpha (sigma = r / 2.05), threshold at 5/255, soften 0.7 px,
 *  fill with the colour and draw it under the picture. `px` converts millimetres to screen pixels. */
export function OutlineFilter({ id, outline, px }: { id: string; outline: Outline; px: number }) {
  const radius = outline.width_mm * PX_PER_MM;
  const screen = px / PX_PER_MM;
  return <svg width="0" height="0" className="absolute" aria-hidden="true" focusable="false">
    <filter id={id} x="-60%" y="-60%" width="220%" height="220%" colorInterpolationFilters="sRGB">
      <feGaussianBlur in="SourceAlpha" stdDeviation={Math.max(0.01, (radius / 2.05) * screen)} result="wide" />
      <feComponentTransfer in="wide" result="mask"><feFuncA type="linear" slope="51" /></feComponentTransfer>
      <feGaussianBlur in="mask" stdDeviation={0.7 * screen} result="soft" />
      <feFlood floodColor={outline.colour} result="ink" />
      <feComposite in="ink" in2="soft" operator="in" result="ring" />
      <feMerge><feMergeNode in="ring" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
  </svg>;
}

/** Path of a rectangle with a semicircular top (`arch`); an arch shorter than half its width is a rounded rectangle. */
export function archPath(w: number, h: number) {
  const r = w / 2;
  if (h < r) return `M0 ${h} V0 H${w} V${h} Z`;
  return `M0 ${h} V${r} A${r} ${r} 0 0 1 ${w} ${r} V${h} Z`;
}

export const shadowStyle = (shadow: Shadow | null | undefined, px: number) =>
  shadow && shadow.opacity_pct > 0
    ? `drop-shadow(${shadow.dx_mm * px}px ${shadow.dy_mm * px}px ${shadow.blur_mm / 2 * px}px ${rgbaCss(shadow.colour, shadow.opacity_pct)})`
    : undefined;
