// One badge drawn to scale from the SAME layers the server compiles and prints (badgeCompile.ts is the twin
// of badge_compile.py), using the card designer's layer views and text fitting. With `interaction`, each item
// gets a hit box: click to select, drag (pointer capture), or arrow keys to nudge (Shift for 5 grid steps).
// Without it the badge is a static picture, for the check-in desk preview and printing.
import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";

import type { CardDocument, Layer, Watermark } from "../../../components/card-designer/cardTypes";
import { CardLayerView } from "../../../components/card-designer/CardLayerView";
import { useCardFonts } from "../../../components/card-designer/useCardFonts";
import { WatermarkView } from "../../../components/card-designer/WatermarkView";
import { compileBadge, type BadgeLayer } from "./badgeCompile";
import { TILE_PADDING_MM, type BadgeElement } from "./badgeGeometry";
import { elementLabels } from "./badgeLabels";
import type { BadgeSettings } from "./badgeNormalize";
import { BadgeSymbol } from "./BadgeSymbol";

export const SAFE_MARGIN_MM = 5;
export type BadgeInteraction = {
  selected: BadgeElement | null;
  onSelect: (element: BadgeElement) => void;
  /** Called once when a drag or nudge starts, so it becomes one undo step. */
  onBeginChange: () => void;
  onMove: (element: BadgeElement, xMm: number, yMm: number) => void;
  showGrid: boolean;
};
/** Real pictures for a printed badge; the designer passes none and shows placeholders. */
export type BadgeImages = { logos?: Record<string, string | null>; photo?: string | null;
  /** Logo sources this event has no picture for: drawn empty, as they print. */
  absent?: string[] };

/** A QR code drawn in the browser (zxing-wasm writer), so badges print offline with no server round trip. */
export function useQrImage(value: string | null) {
  const [image, setImage] = useState<{ value: string; url: string } | null>(null);
  useEffect(() => {
    if (!value) return;
    let active = true; let url: string | undefined;
    void import("zxing-wasm/writer").then(async (writer) => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(value, { format: "QRCode", scale: 8, addQuietZones: false });
      if (active && result.image) { url = URL.createObjectURL(result.image); setImage({ value, url }); }
    }).catch(() => undefined);
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [value]);
  return image?.value === value ? image.url : null;
}

function LogoTile({ layer, images, mono, symbol }: { layer: BadgeLayer; images?: BadgeImages; mono: boolean; symbol: "ink" | "full" }) {
  const source = String(layer.source ?? "");
  if (source === "symbol") return <BadgeSymbol variant={symbol} mono={mono} />;
  if (images?.absent?.includes(source)) return null;
  const url = images?.logos?.[source] ?? null;
  const tile = layer.tile ? { background: "#FFFFFF" } : undefined;
  if (url) return <div className="h-full w-full" style={tile}><img src={url} alt="" className="h-full w-full object-contain" style={{ filter: mono ? "grayscale(1)" : undefined }} /></div>;
  const sponsor = /^sponsor_(\d)$/.exec(source);
  const name = sponsor ? t`Sponsor ${sponsor[1]}` : source === "event" ? t`Event logo` : t`Logo`;
  return <div className="grid h-full w-full place-items-center overflow-hidden rounded-[2px] border border-dashed border-[#9AA9A6] text-center text-[9px] leading-tight text-[#4A5F5C]"
    style={tile}>{name}</div>;
}

function QrMark({ url }: { url: string | null }) {
  if (url) return <img src={url} alt="" className="h-full w-full" style={{ imageRendering: "pixelated" }} />;
  return <svg viewBox="0 0 21 21" className="h-full w-full" shapeRendering="crispEdges" aria-hidden="true">
    {Array.from({ length: 441 }, (_v, i) => [i % 21, Math.floor(i / 21)] as const)
      .filter(([x, y]) => (x * 7 + y * 3) % 5 < 2 || ((x < 7 || x > 13) && y < 7) || (x < 7 && y > 13))
      .map(([x, y]) => <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill="#000000" />)}
  </svg>;
}

function itemBoxes(layers: BadgeLayer[]) {
  const boxes = new Map<BadgeElement, { x: number; y: number; right: number; bottom: number }>();
  for (const layer of layers) {
    if (!layer.element) continue;
    const box = boxes.get(layer.element);
    const right = layer.x_mm + layer.w_mm, bottom = layer.y_mm + layer.h_mm;
    boxes.set(layer.element, box ? { x: Math.min(box.x, layer.x_mm), y: Math.min(box.y, layer.y_mm),
      right: Math.max(box.right, right), bottom: Math.max(box.bottom, bottom) } : { x: layer.x_mm, y: layer.y_mm, right, bottom });
  }
  return boxes;
}

export function BadgeCanvas({ settings, values, pxPerMm, designId, qrValue = null, images, interaction, fieldLabels, eventAccent }: {
  settings: BadgeSettings; values: Record<string, string>; pxPerMm: number; designId: number; qrValue?: string | null;
  images?: BadgeImages; interaction?: BadgeInteraction; fieldLabels?: Record<string, string>; eventAccent?: string | null;
}) {
  const compiled = useMemo(() => compileBadge(settings, { eventAccent, fieldLabels }), [settings, eventAccent, fieldLabels]);
  const fontDocument = useMemo(() => [{ front: { layers: compiled.layers }, back: { layers: [] } } as unknown as CardDocument], [compiled.layers]);
  useCardFonts(designId, fontDocument);
  const qr = useQrImage(settings.showQr ? qrValue : null);
  const [drag, setDrag] = useState<{ element: BadgeElement; x: number; y: number; origin: { xMm: number; yMm: number } } | null>(null);
  const px = pxPerMm;
  const mono = compiled.mono;
  const labels = elementLabels();
  const live = images?.photo ? { photo: images.photo, logos: {}, assets: {}, desk_qr: null, verify_qr: null } : undefined;
  const grid = interaction?.showGrid ? settings.gridSizeMm * px : 0;

  const hitProps = (element: BadgeElement) => interaction ? {
    role: "button" as const, tabIndex: 0, "aria-pressed": interaction.selected === element,
    "aria-label": t`${labels[element]}. Arrow keys move it; hold Shift for bigger steps.`,
    onPointerDown: (event: PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      interaction.onSelect(element);
      interaction.onBeginChange();
      setDrag({ element, x: event.clientX, y: event.clientY, origin: settings.elementPositions[element] });
    },
    onPointerMove: (event: PointerEvent<HTMLDivElement>) => {
      if (!drag || drag.element !== element) return;
      interaction.onMove(element, drag.origin.xMm + (event.clientX - drag.x) / px, drag.origin.yMm + (event.clientY - drag.y) / px);
    },
    onPointerUp: () => setDrag(null), onPointerCancel: () => setDrag(null),
    onFocus: () => interaction.onSelect(element),
    onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => {
      const step = event.shiftKey ? settings.gridSizeMm * 5 : settings.gridSizeMm;
      const move = ({ ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] } as Record<string, number[]>)[event.key];
      if (!move) return;
      event.preventDefault();
      interaction.onBeginChange();
      const at = settings.elementPositions[element];
      interaction.onMove(element, at.xMm + move[0], at.yMm + move[1]);
    },
  } : {};

  return <div data-badge-preview="" className="relative shrink-0 select-none overflow-hidden"
    style={{ width: compiled.page_width_mm * px, height: compiled.page_height_mm * px, background: compiled.background,
      outline: "1px solid rgb(20 44 42 / 14%)", printColorAdjust: "exact", WebkitPrintColorAdjust: "exact",
      backgroundImage: grid ? "linear-gradient(to right, rgb(0 110 99 / 10%) 1px, transparent 1px), linear-gradient(to bottom, rgb(0 110 99 / 10%) 1px, transparent 1px)" : undefined,
      backgroundSize: grid ? `${grid}px ${grid}px` : undefined }}>
    <WatermarkView watermark={compiled.watermark as Watermark} widthMm={compiled.page_width_mm} heightMm={compiled.page_height_mm}
      px={px} mono={mono} designId={designId} imageUrl={null} />
    {compiled.layers.map((layer) => <div key={layer.id} aria-hidden="true" className="pointer-events-none absolute"
      style={{ left: layer.x_mm * px, top: layer.y_mm * px, width: layer.w_mm * px, height: layer.h_mm * px }}>
      {layer.kind === "checkin_qr" ? <div className="h-full w-full bg-white" style={{ padding: TILE_PADDING_MM * px }}><QrMark url={qr} /></div>
        : layer.kind === "logo" ? <LogoTile layer={layer} images={images} mono={mono} symbol={compiled.palette.symbol} />
          : <CardLayerView layer={(layer.kind === "data_field" ? { ...layer, text: `{{${String(layer.field)}}}` } : layer) as unknown as Layer}
            px={px} values={values} designId={designId} mono={mono} live={live} />}
    </div>)}
    {interaction ? <>
      <span aria-hidden="true" className="pointer-events-none absolute border border-dashed" style={{ inset: SAFE_MARGIN_MM * px,
        borderColor: "rgb(0 110 99 / 40%)" }} />
      {[...itemBoxes(compiled.layers)].map(([element, box]) => <div key={element} {...hitProps(element)}
        data-selected={interaction.selected === element ? "" : undefined}
        className="absolute cursor-grab touch-none outline-offset-2 hover:outline hover:outline-1 hover:outline-[#006E63] focus-visible:outline-2 focus-visible:outline-[#006E63] data-[selected]:outline data-[selected]:outline-2 data-[selected]:outline-[#006E63]"
        style={{ left: box.x * px, top: box.y * px, width: (box.right - box.x) * px, height: (box.bottom - box.y) * px,
          zIndex: interaction.selected === element ? 3 : 2 }} />)}
    </> : null}
  </div>;
}
