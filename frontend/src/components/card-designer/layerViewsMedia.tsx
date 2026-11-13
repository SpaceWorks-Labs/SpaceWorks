// Image, photo and shape layers of the studio: framing (zoom and focal point), masks, sticker outline,
// shadow, gradients. Static drawing; the canvas adds interaction.
import { useId } from "react";

import type { Layer } from "./cardTypes";
import { usePhotoFilter } from "./layerExtras";
import { pickPhoto, SAMPLE_PHOTO, type PhotoState } from "./photoVariant";
import { imageFrameStyle, maskCss, polygonPoints, POLYGON_SHAPES, roundedRadius } from "./studioMath";
import { archPath, OutlineFilter, shadowStyle, useGradientDef } from "./studioSvg";

/** A head-and-shoulders silhouette used as the designer's sample cut-out. */
export function SampleCutout({ colour }: { colour: string }) {
  return <svg viewBox="0 0 100 125" className="h-full w-full" aria-hidden="true" preserveAspectRatio="xMidYMax meet">
    <ellipse cx="50" cy="40" rx="21" ry="25" fill={colour} />
    <path d="M6 125 C8 92 28 76 50 76 C72 76 92 92 94 125 Z" fill={colour} />
  </svg>;
}

type PhotoProps = { layer: Layer; px: number; values: Record<string, string>; mono: boolean; photo: string | null;
  /** The person on the card: their cut-out and choice, or a sample person (silhouette). */ state?: PhotoState };

export function PhotoLayerView({ layer, px, values, mono, photo, state = SAMPLE_PHOTO }: PhotoProps) {
  const { filter, defs } = usePhotoFilter(layer, mono);
  const id = `o${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  // A cut-out is drawn unmasked (its alpha is the shape); with none ready the original is used, masked (server rule).
  const pick = pickPhoto(layer.variant, state);
  const useCutout = pick !== "original";
  const mask = useCutout ? {} : maskCss(layer.shape === "circle" || layer.shape === "arch" ? layer.shape
    : layer.shape === "square" ? undefined : "rounded", layer.w_mm, layer.h_mm, px, layer.radius_mm);
  const frame = imageFrameStyle("cover", layer.zoom, layer.focal_x_pct, layer.focal_y_pct);
  const flip = `${layer.flip_x ? "scaleX(-1) " : ""}${layer.flip_y ? "scaleY(-1)" : ""}`.trim();
  const transform = `${frame.transform ?? ""} ${flip}`.trim() || undefined;
  const initials = (values.name ?? "").split(/\s+/).slice(0, 2).map((word) => word[0] ?? "").join("").toUpperCase();
  let body;
  if (pick === "cutout") {
    // Same framing as the server: cover, zoom and focal point inside the box, then the flips.
    body = <div className="h-full w-full overflow-hidden"><img src={state.cutout!} alt="" style={{ ...frame, transform, filter }} /></div>;
  } else if (pick === "silhouette") {
    body = <SampleCutout colour={mono ? "#9A9A9A" : "#2F8F83"} />;
  } else if (photo) {
    body = <div className="h-full w-full overflow-hidden" style={mask}>
      <img src={photo} alt="" style={{ ...frame, transform, filter }} /></div>;
  } else {
    body = <div className="grid h-full w-full place-items-center font-bold" style={{ ...mask, fontSize: layer.h_mm * px * 0.36,
      background: mono ? "#E6E6E6" : "#D7E9E5", color: mono ? "#000000" : "#142C2A" }}>{initials}</div>;
  }
  return <div className="h-full w-full" style={{ filter: shadowStyle(layer.shadow, px) }}>
    {defs}
    {layer.outline ? <OutlineFilter id={id} outline={layer.outline} px={px} /> : null}
    <div className="h-full w-full" style={{ filter: layer.outline ? `url(#${id})` : undefined }}>{body}</div>
  </div>;
}

export function ImageLayerView({ layer, px, url, mono }: { layer: Layer; px: number; url: string | null; mono: boolean }) {
  const id = `o${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const frame = imageFrameStyle(layer.fit ?? "contain", layer.zoom, layer.focal_x_pct, layer.focal_y_pct);
  const flip = `${layer.flip_x ? "scaleX(-1) " : ""}${layer.flip_y ? "scaleY(-1)" : ""}`.trim();
  const transform = `${frame.transform ?? ""} ${flip}`.trim() || undefined;
  if (!url) return <div className="h-full w-full bg-surface" />;
  return <div className="h-full w-full" style={{ filter: shadowStyle(layer.shadow, px) }}>
    {layer.outline ? <OutlineFilter id={id} outline={layer.outline} px={px} /> : null}
    <div className="h-full w-full" style={{ filter: layer.outline ? `url(#${id})` : undefined }}>
      <div className="h-full w-full overflow-hidden" style={maskCss(layer.mask, layer.w_mm, layer.h_mm, px, layer.radius_mm)}>
        <img src={url} alt="" style={{ ...frame, transform, filter: mono ? "grayscale(1)" : undefined }} />
      </div>
    </div>
  </div>;
}

/** Shapes are drawn as SVG when they use a v3 feature (gradient, arch, circle, rounded, shadow). */
export function usesSvgShape(layer: Layer) {
  return layer.shape === "arch" || layer.shape === "circle" || layer.shape === "rounded" || Boolean(layer.fill_gradient)
    || (POLYGON_SHAPES as readonly string[]).includes(layer.shape ?? "")
    || Boolean(layer.shadow) || Boolean(layer.flip_x || layer.flip_y);
}

export function ShapeSvg({ layer, px, mono }: { layer: Layer; px: number; mono: boolean }) {
  const { w_mm: w, h_mm: h } = layer;
  const [gradientId, def] = useGradientDef(mono ? null : layer.fill_gradient, w, h);
  const stroke = typeof layer.stroke === "string" ? layer.stroke : null;
  const sw = layer.stroke_mm ?? 0.3;
  const fill = gradientId ? `url(#${gradientId})` : layer.fill ?? "none";
  const common = { fill: mono && layer.fill ? "#DDDDDD" : fill, stroke: stroke ?? undefined, strokeWidth: stroke ? sw : undefined };
  const radius = layer.shape === "rounded" ? roundedRadius(w, h, layer.radius_mm && layer.radius_mm > 0 ? layer.radius_mm : 3)
    : layer.radius_mm ?? 0;
  const flip = `${layer.flip_x ? `translate(${w} 0) scale(-1 1) ` : ""}${layer.flip_y ? `translate(0 ${h}) scale(1 -1)` : ""}`.trim();
  let shape;
  if (layer.shape === "ellipse") shape = <ellipse cx={w / 2} cy={h / 2} rx={w / 2} ry={h / 2} {...common} />;
  else if (layer.shape === "circle") shape = <circle cx={w / 2} cy={h / 2} r={Math.min(w, h) / 2} {...common} />;
  else if (layer.shape === "arch") shape = <path d={archPath(w, h)} {...common} />;
  else if ((POLYGON_SHAPES as readonly string[]).includes(layer.shape ?? "")) {
    shape = <polygon points={polygonPoints(layer.shape!, w, h).map(([x, y]) => `${x},${y}`).join(" ")} {...common} />;
  }
  else if (layer.shape === "line") shape = <line x1={0} y1={h / 2} x2={w} y2={h / 2} stroke={stroke ?? layer.fill ?? "#000000"} strokeWidth={sw} />;
  else shape = <rect width={w} height={h} rx={radius} {...common} />;
  return <svg width={w * px} height={h * px} viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible", display: "block",
    filter: shadowStyle(layer.shadow, px) }} aria-hidden="true">
    <defs>{def}</defs><g transform={flip || undefined}>{shape}</g>
  </svg>;
}
