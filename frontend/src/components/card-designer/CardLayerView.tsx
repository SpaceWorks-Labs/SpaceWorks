import { useEffect, useState, type CSSProperties } from "react";

import { staffRequestBlob } from "../../lib/api";
import type { Background, Layer } from "./cardTypes";
import { PT_TO_MM } from "./cardGeometry";
import { merge } from "./dataFields";
import { assetUrlPath } from "./designerApi";
import { BarcodeView, useFittedText, usePhotoFilter } from "./layerExtras";

const assetCache = new Map<string, Promise<string>>();

export function useAssetUrl(designId: number, assetId: string | undefined | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!assetId) { setUrl(null); return; }
    const key = `${designId}:${assetId}`;
    if (!assetCache.has(key)) {
      assetCache.set(key, staffRequestBlob(assetUrlPath(designId, assetId)).then((blob) => URL.createObjectURL(blob)));
    }
    let live = true;
    assetCache.get(key)!.then((value) => { if (live) setUrl(value); }).catch(() => { if (live) setUrl(null); });
    return () => { live = false; };
  }, [designId, assetId]);
  return url;
}

export function backgroundStyle(background: Background, imageUrl: string | null): CSSProperties {
  if (background.kind === "colour") return { background: background.colour };
  if (background.kind === "gradient") {
    const stops = background.stops.map((stop) => `${stop.colour} ${stop.at}%`).join(", ");
    return { background: background.type === "radial" ? `radial-gradient(circle, ${stops})`
      : `linear-gradient(${background.angle_deg}deg, ${stops})` };
  }
  const dim = background.dim_pct / 100;
  return { backgroundColor: background.fallback ?? "#FFFFFF",
    backgroundImage: imageUrl ? `linear-gradient(rgba(0,0,0,${dim}), rgba(0,0,0,${dim})), url(${imageUrl})` : undefined,
    backgroundSize: background.fit, backgroundPosition: "center", backgroundRepeat: "no-repeat" };
}

function QrPlaceholder() {
  return <div className="grid h-full w-full place-items-center bg-white p-[8%]" aria-hidden="true">
    <svg viewBox="0 0 21 21" className="h-full w-full" shapeRendering="crispEdges">
      {Array.from({ length: 21 * 21 }, (_v, i) => [i % 21, Math.floor(i / 21)] as const)
        .filter(([x, y]) => (x * 7 + y * 3) % 5 < 2 || ((x < 7 || x > 13) && y < 7) || (x < 7 && y > 13))
        .map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill="#142C2A" />)}
    </svg>
  </div>;
}

/** Real images for a holder's own card (the printed-card view); the designer passes none and shows placeholders. */
export type LiveImages = { photo: string | null; logos: Record<string, string | null>; assets: Record<string, string | null>;
  desk_qr: string | null; verify_qr: string | null; barcodes?: Record<string, string | null> };

function TextLayerView({ layer, px, values, mono }: { layer: Layer; px: number; values: Record<string, string>; mono: boolean }) {
  const text = merge(layer.text ?? "", values);
  const fitted = useFittedText(layer, text, px);
  return <div className="h-full w-full overflow-hidden" style={{ ...fitted,
    lineHeight: layer.line_height ?? 1.2, color: mono ? "#000000" : layer.colour, textAlign: layer.align,
    textTransform: layer.uppercase ? "uppercase" : undefined, letterSpacing: (layer.tracking_pt ?? 0) * PT_TO_MM * px,
    display: "flex", flexDirection: "column", overflowWrap: "anywhere",
    justifyContent: { top: "flex-start", middle: "center", bottom: "flex-end" }[layer.valign ?? "top"] }}>{text}</div>;
}

function PhotoLayerView({ layer, px, values, mono, photo }: { layer: Layer; px: number; values: Record<string, string>;
  mono: boolean; photo: string | null }) {
  const { filter, defs } = usePhotoFilter(layer, mono);
  const radius = layer.shape === "circle" ? "50%" : layer.shape === "rounded" ? "14%" : 0;
  if (photo) return <>{defs}<img src={photo} alt="" className="h-full w-full object-cover" style={{ filter, borderRadius: radius }} /></>;
  const initials = (values.name ?? "").split(/\s+/).slice(0, 2).map((word) => word[0] ?? "").join("").toUpperCase();
  return <div className="grid h-full w-full place-items-center font-bold" style={{ borderRadius: radius,
    fontSize: layer.h_mm * px * 0.36, background: mono ? "#E6E6E6" : "#D7E9E5", color: mono ? "#000000" : "#142C2A" }}>{initials}</div>;
}

/** One layer drawn to scale: `px` converts millimetres to CSS pixels. Static; the canvas adds interaction. */
export function CardLayerView({ layer, px, values, designId, mono, live }: { layer: Layer; px: number;
  values: Record<string, string>; designId: number; mono: boolean; live?: LiveImages }) {
  const fetched = useAssetUrl(designId, !live && layer.kind === "image" ? layer.asset_id : null);
  const imageUrl = live ? (layer.asset_id ? live.assets[layer.asset_id] ?? null : null) : fetched;
  const grey = mono ? "grayscale(1)" : undefined;
  if (layer.kind === "text" || layer.kind === "data_field") return <TextLayerView layer={layer} px={px} values={values} mono={mono} />;
  if (layer.kind === "barcode") {
    return <BarcodeView layer={layer} values={values} image={live ? live.barcodes?.[layer.source ?? "number"] ?? null : null} />;
  }
  if (layer.kind === "photo") return <PhotoLayerView layer={layer} px={px} values={values} mono={mono} photo={live?.photo ?? null} />;
  if (layer.kind === "shape" || layer.kind === "band") {
    if (layer.shape === "line") return <div className="h-full w-full" style={{ borderTop: `${Math.max(1, (layer.stroke_mm ?? 0.3) * px)}px solid ${layer.stroke ?? layer.fill}`, marginTop: "50%" }} />;
    return <div className="h-full w-full" style={{ background: layer.fill ?? "transparent",
      border: layer.stroke ? `${Math.max(1, (layer.stroke_mm ?? 0.3) * px)}px solid ${layer.stroke}` : undefined,
      borderRadius: layer.shape === "ellipse" ? "50%" : (layer.radius_mm ?? 0) * px }} />;
  }
  if (layer.kind === "perforation") {
    const vertical = layer.orientation !== "horizontal";
    return <div className="h-full w-full" style={{ [vertical ? "borderLeft" : "borderTop"]: `1px dashed ${layer.colour}`,
      marginLeft: vertical ? "50%" : undefined, marginTop: vertical ? undefined : "50%" }} />;
  }
  if (layer.kind === "desk_qr" || layer.kind === "verify_qr") {
    const qr = live?.[layer.kind];
    return qr ? <div className="h-full w-full bg-white"><img src={qr} alt="" className="h-full w-full" /></div> : <QrPlaceholder />;
  }
  if (layer.kind === "logo" && live) {
    const logo = live.logos[layer.source ?? "space"];
    return logo ? <div className="h-full w-full" style={{ background: layer.tile ? "#FFFFFF" : undefined }}>
      <img src={logo} alt="" className="h-full w-full object-contain" style={{ filter: grey }} /></div> : null;
  }
  if (layer.kind === "image") {
    return imageUrl ? <img src={imageUrl} alt="" className="h-full w-full" style={{ objectFit: layer.fit ?? "contain", filter: grey }} />
      : <div className="h-full w-full bg-surface" />;
  }
  return <div className="grid h-full w-full place-items-center rounded-control border border-dashed border-line text-[10px] text-muted"
    style={{ background: layer.tile ? "#FFFFFF" : undefined }}>{layer.source === "symbol" ? "Symbol" : `${layer.source} logo`}</div>;
}
