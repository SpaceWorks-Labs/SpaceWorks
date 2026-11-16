// Pure geometry and colour helpers for the Card Studio's backgrounds, overlays, images, masks and
// shadows. The TypeScript twin of the server's plan (spec sections 2-7): every rule here has the
// same formula in apps/card_designs/studio_plan.py, so a browser preview matches the printed card.
import type { GradientSpec, GradientStop, MaskShape, Outline, Shadow } from "./cardTypes";

export const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
/** Working raster of the server (300 dpi) in pixels per millimetre. */
export const PX_PER_MM = 11.81;

export function hexToRgb(hex: string): [number, number, number] {
  const clean = /^#[0-9a-f]{6}$/i.test(hex) ? hex.slice(1) : "000000";
  return [0, 2, 4].map((offset) => parseInt(clean.slice(offset, offset + 2), 16)) as [number, number, number];
}
export const rgbaCss = (hex: string, alphaPct = 100) => {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${Math.round(cssNumber(alphaPct, 100, 0, 100) * 10) / 1000})`;
};
/**
 * Document colours and numbers never reach CSS as raw text. The server only stores `#RRGGBB` and
 * ranged numbers, but a row that skipped it must not turn `red 0%), url(https://x/?b), …` into a
 * third-party request: colours become `rgb()` (anything else reads as black) and numbers are
 * coerced with Number() and clamped (non-numbers take the fallback).
 */
export const rgbCss = (hex: unknown) => {
  const [r, g, b] = hexToRgb(typeof hex === "string" ? hex : "");
  return `rgb(${r}, ${g}, ${b})`;
};
export function cssNumber(value: unknown, fallback: number, low: number, high: number) {
  const number = typeof value === "number" || typeof value === "string" ? Number(value) : Number.NaN;
  return Number.isFinite(number) ? clamp(number, low, high) : fallback;
}

/** Stops sorted by position with positions clamped to 0-100 (the server's rule). */
export const sortedStops = (stops: GradientStop[]) =>
  stops.map((stop) => ({ ...stop, at: clamp(stop.at, 0, 100) })).sort((a, b) => a.at - b.at);

/** Straight (non-premultiplied) sRGB interpolation, sampled into many stops so the browser's own
 *  premultiplied blending cannot drift from the server (spec section 2: overlay alpha). */
export function sampleStops(stops: GradientStop[], samples = 24): GradientStop[] {
  const sorted = sortedStops(stops);
  if (sorted.length < 2) return sorted;
  const out: GradientStop[] = [];
  for (let i = 0; i < samples; i += 1) {
    const at = (100 * i) / (samples - 1);
    const next = sorted.findIndex((stop) => stop.at >= at);
    const hi = next < 0 ? sorted[sorted.length - 1] : sorted[next];
    const lo = next <= 0 ? sorted[0] : sorted[next - 1];
    const span = hi.at - lo.at;
    const f = span <= 0 || next < 0 ? (next < 0 ? 1 : 0) : (at - lo.at) / span;
    const a = hexToRgb(lo.colour), b = hexToRgb(hi.colour);
    const rgb = a.map((value, index) => Math.round(value + (b[index] - value) * f));
    const alpha = (lo.alpha_pct ?? 100) + ((hi.alpha_pct ?? 100) - (lo.alpha_pct ?? 100)) * f;
    out.push({ colour: `#${rgb.map((value) => value.toString(16).padStart(2, "0")).join("").toUpperCase()}`, at, alpha_pct: alpha });
  }
  return out;
}

/** A CSS gradient for `spec` on a page of `widthMm` x `heightMm`. Radial radius is a share of half the diagonal. */
export function gradientCss(spec: GradientSpec, widthMm: number, heightMm: number, withAlpha = false) {
  const stops = (withAlpha ? sampleStops(spec.stops) : sortedStops(spec.stops));
  const list = stops.map((stop) => `${withAlpha ? rgbaCss(stop.colour, stop.alpha_pct ?? 100) : rgbCss(stop.colour)} ${Math.round(cssNumber(stop.at, 0, 0, 100) * 100) / 100}%`).join(", ");
  if (spec.type === "radial") {
    const radius = cssNumber(spec.radius_pct, 100, 10, 300) / 100 * Math.hypot(cssNumber(widthMm, 0, 0, 1000), cssNumber(heightMm, 0, 0, 1000)) / 2;
    return `radial-gradient(circle ${Math.max(0.01, radius)}mm at ${cssNumber(spec.cx_pct, 50, 0, 100)}% ${cssNumber(spec.cy_pct, 50, 0, 100)}%, ${list})`;
  }
  return `linear-gradient(${cssNumber(spec.angle_deg, 0, 0, 360)}deg, ${list})`;
}

export type Box = { x: number; y: number; w: number; h: number };

/** Where an image of `imageW` x `imageH` lands inside a box (spec section 2 position rule): the base fit size
 *  times `zoom`, then offset by (free space) x focal / 100, like CSS `object-position`. */
export function imageBox(boxW: number, boxH: number, imageW: number, imageH: number,
  fit: "cover" | "contain" | "stretch", zoom = 1, focalX = 50, focalY = 50): Box {
  if (imageW <= 0 || imageH <= 0) return { x: 0, y: 0, w: boxW, h: boxH };
  let w = boxW, h = boxH;
  if (fit !== "stretch") {
    const scale = fit === "cover" ? Math.max(boxW / imageW, boxH / imageH) : Math.min(boxW / imageW, boxH / imageH);
    w = imageW * scale; h = imageH * scale;
  }
  w *= clamp(zoom, 1, 4); h *= clamp(zoom, 1, 4);
  return { x: (boxW - w) * clamp(focalX, 0, 100) / 100, y: (boxH - h) * clamp(focalY, 0, 100) / 100, w, h };
}

/** Style for an <img> that fills its box: object-fit by `fit`, the focal point as object-position, and `zoom`
 *  as a scale about that same point. Algebraically the spec's rule: offset = (box - base x zoom) x focal. */
export function imageFrameStyle(fit: "cover" | "contain" | "stretch", zoom = 1, focalX = 50, focalY = 50) {
  const fx = clamp(focalX, 0, 100), fy = clamp(focalY, 0, 100), z = clamp(zoom, 1, 4);
  return { width: "100%", height: "100%", objectFit: (fit === "stretch" ? "fill" : fit) as "fill" | "cover" | "contain",
    objectPosition: `${fx}% ${fy}%`, transformOrigin: `${fx}% ${fy}%`, transform: z === 1 ? undefined : `scale(${z})` };
}

/** Radius a rounded mask uses: `radius_mm`, else 14 % of the shorter side. */
/** Twin of studio_geometry.mask_radius: the layer's own radius (0 = square corners), else 14 % of the shorter side. */
export const roundedRadius = (w: number, h: number, radius: number | null | undefined) =>
  Math.min(typeof radius === "number" && Number.isFinite(radius) ? Math.max(0, radius) : Math.min(w, h) * 0.14, w / 2, h / 2);

/** CSS clip for a mask inside a w x h mm box (px = pixels per mm). `none` returns no clip. */
export function maskCss(mask: MaskShape | "square" | undefined, w: number, h: number, px: number,
  radius?: number | null): { borderRadius?: string; clipPath?: string } {
  switch (mask) {
    case "rounded": return { borderRadius: `${roundedRadius(w, h, radius) * px}px` };
    case "circle": {
      const d = Math.min(w, h);
      return d === w && d === h ? { borderRadius: "50%" } : { clipPath: `circle(${d / 2 * px}px at 50% 50%)` };
    }
    case "arch": {
      if (h < w / 2) return { borderRadius: `${roundedRadius(w, h, radius) * px}px` };
      return { borderRadius: `${w / 2 * px}px ${w / 2 * px}px 0 0` };
    }
    default: return {};
  }
}

/** `drop-shadow` filter for raster layers (sigma = blur / 2, like the server's Gaussian). */
export function shadowFilter(shadow: Shadow | null | undefined, px: number) {
  if (!shadow || shadow.opacity_pct <= 0) return undefined;
  return `drop-shadow(${shadow.dx_mm * px}px ${shadow.dy_mm * px}px ${shadow.blur_mm / 2 * px}px ${rgbaCss(shadow.colour, shadow.opacity_pct)})`;
}

/** CSS text-shadow: a 9-sample stack in spirit; the browser's blur stands in for it. */
export function textShadowCss(shadow: Shadow | null | undefined, px: number) {
  if (!shadow || shadow.opacity_pct <= 0) return undefined;
  return `${shadow.dx_mm * px}px ${shadow.dy_mm * px}px ${Math.min(2, shadow.blur_mm) * px}px ${rgbaCss(shadow.colour, shadow.opacity_pct)}`;
}

/** Sticker outline: stacked drop-shadows trace the alpha silhouette at `width` mm in every direction. */
export function outlineFilter(outline: Outline | null | undefined, px: number) {
  if (!outline || outline.width_mm <= 0) return undefined;
  const r = outline.width_mm * px;
  const steps = 12;
  return Array.from({ length: steps }, (_v, i) => {
    const angle = (2 * Math.PI * i) / steps;
    return `drop-shadow(${(Math.cos(angle) * r).toFixed(2)}px ${(Math.sin(angle) * r).toFixed(2)}px 0 ${outline.colour})`;
  }).join(" ");
}

/** Pixels the server dilates a cut-out's alpha by for a sticker outline. */
export const outlinePx = (outline: Outline | null | undefined) => (outline ? Math.round(outline.width_mm * PX_PER_MM) : 0);

/** The box a layer occupies including its outline (the server's geometry check counts the outline as part of the layer). */
export function paintedBox(box: Box, outline: Outline | null | undefined): Box {
  const w = outline?.width_mm ?? 0;
  return { x: box.x - w, y: box.y - w, w: box.w + 2 * w, h: box.h + 2 * w };
}

/** Start and end of a linear gradient across a w x h box, CSS angle convention (0deg = up); twin of `gradient_line`. */
/** Vertices of a polygon shape in its box, top-left origin, 3 decimals: the twin of studio_geometry.polygon_points. */
export function polygonPoints(shape: string, w: number, h: number): [number, number][] {
  let points: [number, number][];
  if (shape === "triangle") points = [[w / 2, 0], [w, h], [0, h]];
  else if (shape === "diamond") points = [[w / 2, 0], [w, h / 2], [w / 2, h], [0, h / 2]];
  else if (shape === "hexagon") points = [[w / 2, 0], [w, h / 4], [w, h * 3 / 4], [w / 2, h], [0, h * 3 / 4], [0, h / 4]];
  else if (shape === "star") {
    points = Array.from({ length: 10 }, (_v, index) => {
      const radius = index % 2 === 0 ? 1 : 0.5, angle = (-90 + index * 36) * Math.PI / 180;
      return [w / 2 + Math.cos(angle) * w / 2 * radius, h / 2 + Math.sin(angle) * h / 2 * radius];
    });
  } else return [];
  return points.map(([x, y]) => [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000]);
}

export const POLYGON_SHAPES = ["triangle", "diamond", "hexagon", "star"] as const;

export function gradientLine(angleDeg: number, w: number, h: number) {
  const angle = (angleDeg * Math.PI) / 180;
  const dx = Math.sin(angle), dy = -Math.cos(angle);
  const half = (Math.abs(w * dx) + Math.abs(h * dy)) / 2;
  return { x0: w / 2 - dx * half, y0: h / 2 - dy * half, x1: w / 2 + dx * half, y1: h / 2 + dy * half };
}

/** Centre and radius of a radial gradient across a w x h box (radius is a share of half the diagonal); twin of `radial_circle`. */
export function radialCircle(cx: number, cy: number, radiusPct: number, w: number, h: number) {
  return { cx: w * cx / 100, cy: h * cy / 100, r: Math.hypot(w, h) / 2 * radiusPct / 100 };
}
