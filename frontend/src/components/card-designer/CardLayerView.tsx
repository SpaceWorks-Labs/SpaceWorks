import { t } from "@lingui/core/macro";
import { useEffect, useState, type CSSProperties } from "react";

import { staffRequestBlob } from "../../lib/api";
import type { Background, Layer } from "./cardTypes";
import { PT_TO_MM } from "./cardGeometry";
import { merge } from "./dataFields";
import { cssNumber, gradientCss, rgbCss } from "./studioMath";
import { assetUrlPath } from "./designerApi";
import { useStudioAssets } from "./studioAssets";
import { CertificateIdView, SealLayerView, SignatureLayerView } from "./layerViewsCertificate";
import { ImageLayerView, PhotoLayerView, ShapeSvg, usesSvgShape } from "./layerViewsMedia";
import type { PhotoState } from "./photoVariant";
import { IconLayerView } from "./IconLayerView";
import { BarcodeView, useFittedText } from "./layerExtras";
import { RichTextLayer } from "./RichTextLayer";
import { isRichText } from "./studioText";

const assetCache = new Map<string, Promise<string>>();

export function useAssetUrl(designId: number, assetId: string | undefined | null) {
  const [url, setUrl] = useState<string | null>(null);
  const assets = useStudioAssets();
  useEffect(() => {
    if (!assetId) { setUrl(null); return; }
    const key = `${assets ? "studio" : designId}:${assetId}`;
    if (!assetCache.has(key)) {
      assetCache.set(key, assets ? assets.load(assetId)
        : staffRequestBlob(assetUrlPath(designId, assetId)).then((blob) => URL.createObjectURL(blob)));
    }
    let live = true;
    assetCache.get(key)!.then((value) => { if (live) setUrl(value); }).catch(() => { if (live) setUrl(null); });
    return () => { live = false; };
  }, [designId, assetId, assets]);
  return url;
}

export function backgroundStyle(background: Background, imageUrl: string | null): CSSProperties {
  if (background.kind === "colour") return { background: rgbCss(background.colour) };
  if (background.kind === "gradient") {
    return { background: gradientCss(background, 85.6, 54) };
  }
  const dim = cssNumber(background.dim_pct, 0, 0, 100) / 100;
  return { backgroundColor: rgbCss(background.fallback ?? "#FFFFFF"),
    backgroundImage: imageUrl ? `linear-gradient(rgba(0,0,0,${dim}), rgba(0,0,0,${dim})), url(${imageUrl})` : undefined,
    backgroundSize: background.fit === "stretch" ? "100% 100%" : background.fit, backgroundPosition: "center", backgroundRepeat: "no-repeat" };
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
/** `photo_cutout` is the holder's cut-out as a data URI; `use_cutout` says whether they chose it (otherwise the original shows). */
export type LiveImages = { photo: string | null; photo_cutout?: string | null; use_cutout?: boolean; logos: Record<string, string | null>; assets: Record<string, string | null>;
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

/** One layer drawn to scale: `px` converts millimetres to CSS pixels. Static; the canvas adds interaction. */
export function CardLayerView({ layer, px, values, designId, mono, live, photoState }: { layer: Layer; px: number;
  values: Record<string, string>; designId: number; mono: boolean; live?: LiveImages;
  /** The designer's "Preview as" person; a holder's own card (`live`) derives it from the live images. */ photoState?: PhotoState }) {
  const fetched = useAssetUrl(designId, !live && layer.kind === "image" ? layer.asset_id : null);
  const imageUrl = live ? (layer.asset_id ? live.assets[layer.asset_id] ?? null : null) : fetched;
  const grey = mono ? "grayscale(1)" : undefined;
  if (layer.kind === "text" || layer.kind === "data_field") {
    return isRichText(layer) ? <RichTextLayer layer={layer} px={px} values={values} mono={mono} locale={values.locale} />
      : <TextLayerView layer={layer} px={px} values={values} mono={mono} />;
  }
  if (layer.kind === "signature" || layer.kind === "signature_row") return <SignatureLayerView layer={layer} px={px} values={values} mono={mono} />;
  if (layer.kind === "seal") return <SealLayerView layer={layer} px={px} mono={mono} />;
  if (layer.kind === "certificate_id") return <CertificateIdView layer={layer} px={px} values={values} mono={mono} />;
  if (layer.kind === "barcode") {
    const source = layer.source ?? "number";
    const image = live ? live.barcodes?.[layer.symbology && layer.symbology !== "code128" ? `${source}:${layer.symbology}` : source] ?? null : null;
    return <BarcodeView layer={layer} values={values} image={image} designId={live ? 0 : designId} />;
  }
  if (layer.kind === "photo") {
    const state = live ? { cutout: live.photo_cutout ?? null, useCutout: Boolean(live.use_cutout), sample: false } : photoState;
    return <PhotoLayerView layer={layer} px={px} values={values} mono={mono} photo={live?.photo ?? null} state={state} />;
  }
  if (layer.kind === "shape" || layer.kind === "band") {
    if (layer.kind === "shape" && usesSvgShape(layer)) return <ShapeSvg layer={layer} px={px} mono={mono} />;
    const stroke = typeof layer.stroke === "string" ? rgbCss(layer.stroke) : null;
    if (layer.shape === "line") return <div className="h-full w-full" style={{ borderTop: `${Math.max(1, (layer.stroke_mm ?? 0.3) * px)}px solid ${stroke ?? rgbCss(layer.fill)}`, marginTop: "50%" }} />;
    return <div className="h-full w-full" style={{ background: layer.fill ? rgbCss(layer.fill) : "transparent",
      border: stroke ? `${Math.max(1, (layer.stroke_mm ?? 0.3) * px)}px solid ${stroke}` : undefined,
      borderRadius: layer.shape === "ellipse" ? "50%" : (layer.radius_mm ?? 0) * px }} />;
  }
  if (layer.kind === "icon") return <IconLayerView layer={layer} mono={mono} />;
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
  if (layer.kind === "image") return <ImageLayerView layer={layer} px={px} url={imageUrl} mono={mono} />;
  return <div className="grid h-full w-full place-items-center rounded-control border border-dashed border-line text-[10px] text-muted"
    style={{ background: layer.tile ? "#FFFFFF" : undefined }}>{layer.source === "symbol" ? t`Symbol` : `${layer.source} logo`}</div>;
}
