import { t } from "@lingui/core/macro";
import type { KeyboardEvent, PointerEvent } from "react";
import { Image, Lock, PenLine, QrCode } from "lucide-react";
import { mergeTags } from "../badgeStocks";
import { layerColour, type Layer } from "../layout";
import type { Corner } from "./geometry";

const PT_MM = 25.4 / 72;
const CORNERS: Corner[] = ["nw", "ne", "sw", "se"];
const CORNER_STYLE: Record<Corner, string> = { nw: "-left-2 -top-2 cursor-nwse-resize", ne: "-right-2 -top-2 cursor-nesw-resize",
  sw: "-bottom-2 -left-2 cursor-nesw-resize", se: "-bottom-2 -right-2 cursor-nwse-resize" };

export function layerLabel(layer: Layer) {
  if (layer.type === "text") return layer.text?.trim() ? t`Text "${layer.text.slice(0, 40)}"` : t`Empty text`;
  if (layer.type === "signature") return t`Signature ${layer.signature_slot ?? 1}`;
  if (layer.type === "certificate_qr") return t`Verification QR`;
  if (layer.type === "certificate_id") return t`Certificate ID`;
  if (layer.type === "event_credential_qr") return t`Check-in QR`;
  return layer.type.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase());
}

type Props = { layer: Layer; scale: number; selected: boolean; values?: Record<string, string>;
  signature?: { name: string; title: string };
  onPointerDown: (event: PointerEvent, mode: "move" | "resize" | "rotate", corner?: Corner) => void;
  onSelect: () => void; onKeyDown: (event: KeyboardEvent) => void };

/** One layer on the canvas: an approximate rendering, keyboard focus, and handles when selected. */
export function CanvasLayer({ layer, scale, selected, values, signature, onPointerDown, onSelect, onKeyDown }: Props) {
  const fontPx = (layer.font_size_pt ?? 12) * PT_MM * scale;
  const colour = layerColour(layer);
  const text = layer.type === "certificate_id" ? "6f1c2a9e-1b2c-4d5e-8f90-123456789abc"
    : values ? mergeTags(layer.text ?? "", values) : layer.text ?? "";
  const textStyle = { fontFamily: layer.font_family ?? "Gilroy", fontWeight: layer.font_weight ?? 400, fontSize: `${fontPx}px`,
    lineHeight: layer.line_height ?? 1.3, letterSpacing: `${(layer.tracking_pt ?? 0) * PT_MM * scale}px`, color: colour,
    textAlign: layer.align ?? "left", textTransform: layer.uppercase ? "uppercase" : "none" } as const;
  return <div className={`absolute ${layer.locked ? "" : "cursor-move"} ${selected ? "z-10" : ""}`}
    style={{ left: layer.x_mm * scale, top: layer.y_mm * scale, width: layer.width_mm * scale, height: layer.height_mm * scale,
      transform: `rotate(${layer.rotation}deg)`, opacity: layer.opacity ?? 1 }}>
    <div role="button" tabIndex={0} aria-pressed={selected}
      aria-label={`${layerLabel(layer)}${layer.locked ? ", locked" : ""}. Arrow keys move, Ctrl+arrows resize, [ and ] rotate, Delete removes.`}
      className={`h-full w-full overflow-hidden outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${selected ? "ring-2 ring-focus" : "ring-1 ring-line/60 hover:ring-outline"}`}
      onPointerDown={(event) => { onSelect(); if (!layer.locked) onPointerDown(event, "move"); }}
      onFocus={onSelect} onKeyDown={onKeyDown}>
      {layer.type === "text" || layer.type === "certificate_id"
        ? <div className="whitespace-pre-wrap break-words" style={textStyle}>{text}</div>
        : layer.type === "signature"
          ? <div className="flex h-full flex-col items-stretch justify-end" style={textStyle}>
            <PenLine aria-hidden="true" className="mx-auto mb-1 opacity-60" style={{ width: fontPx * 2, height: fontPx * 2, color: colour }} />
            <div style={{ borderTop: `1px solid ${colour}` }} />
            <div className="truncate" style={{ fontWeight: layer.font_weight ?? 600 }}>{signature?.name ?? t`Signatory`}</div>
            <div className="truncate" style={{ fontWeight: 400, fontSize: fontPx * 0.8 }}>{signature?.title ?? ""}</div></div>
          : <div className="flex h-full w-full items-center justify-center bg-panel/70 text-xs font-semibold text-muted">
            {layer.type.endsWith("qr") ? <QrCode aria-hidden="true" size={Math.min(48, layer.width_mm * scale * 0.6)} />
              : <Image aria-hidden="true" size={Math.min(40, layer.height_mm * scale * 0.5)} />}
            <span className="sr-only">{layerLabel(layer)}</span></div>}
    </div>
    {layer.locked && selected ? <Lock aria-hidden="true" size={14} className="absolute -right-5 -top-5 text-muted" /> : null}
    {selected && !layer.locked ? <>
      {CORNERS.map((corner) => <span key={corner} aria-hidden="true"
        className={`absolute h-4 w-4 rounded-full border-2 border-focus bg-surface ${CORNER_STYLE[corner]}`}
        onPointerDown={(event) => { event.stopPropagation(); onPointerDown(event, "resize", corner); }} />)}
      <span aria-hidden="true" className="absolute -top-8 left-1/2 h-4 w-4 -translate-x-1/2 cursor-grab rounded-full border-2 border-focus bg-surface"
        onPointerDown={(event) => { event.stopPropagation(); onPointerDown(event, "rotate"); }} />
      <span aria-hidden="true" className="absolute -top-4 left-1/2 h-4 w-px -translate-x-1/2 bg-focus" />
    </> : null}
  </div>;
}
