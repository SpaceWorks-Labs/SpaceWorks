import { t } from "@lingui/core/macro";
import { ArrowDown, ArrowUp, Copy, Eye, EyeOff, Lock, LockOpen, Trash2 } from "lucide-react";
import type { Layer } from "../layout";
import { layerLabel } from "./CanvasLayer";

const PROTECTED: Layer["type"][] = ["certificate_qr", "certificate_id", "event_credential_qr"];

/** Layers top to bottom of the stack order, each with select, z-order, lock, hide, duplicate and delete. */
export function LayerList({ layers, selectedId, onSelect, onMove, onToggle, onDuplicate, onDelete }: {
  layers: Layer[]; selectedId?: string; onSelect: (id: string) => void; onMove: (from: number, to: number) => void;
  onToggle: (id: string, key: "locked" | "hidden") => void; onDuplicate: (id: string) => void; onDelete: (id: string) => void;
}) {
  const full = layers.length >= 20;
  return <ol className="grid gap-2" aria-label={t`Layers (first prints underneath)`}>{layers.map((layer, index) => {
    const name = `${index + 1}. ${layerLabel(layer)}`;
    return <li key={layer.id} className={`flex flex-wrap items-center gap-1 rounded-control border p-1 ${layer.id === selectedId ? "border-focus bg-panel" : "border-line"}`}>
      <button type="button" className={`desk-button min-h-11 min-w-0 flex-1 justify-start truncate ${layer.hidden ? "text-muted line-through" : ""}`}
        aria-pressed={layer.id === selectedId} onClick={() => onSelect(layer.id)}>{name}</button>
      <button className="desk-button min-h-11 min-w-11" type="button" aria-label={t`Send ${name} backward`} disabled={index === 0} onClick={() => onMove(index, index - 1)}><ArrowUp size={16} aria-hidden="true" /></button>
      <button className="desk-button min-h-11 min-w-11" type="button" aria-label={t`Bring ${name} forward`} disabled={index === layers.length - 1} onClick={() => onMove(index, index + 1)}><ArrowDown size={16} aria-hidden="true" /></button>
      <button className="desk-button min-h-11 min-w-11" type="button" aria-pressed={Boolean(layer.locked)} aria-label={`${layer.locked ? "Unlock" : "Lock"} ${name}`} onClick={() => onToggle(layer.id, "locked")}>
        {layer.locked ? <Lock size={16} aria-hidden="true" /> : <LockOpen size={16} aria-hidden="true" />}</button>
      <button className="desk-button min-h-11 min-w-11" type="button" aria-pressed={Boolean(layer.hidden)} disabled={PROTECTED.includes(layer.type)}
        aria-label={PROTECTED.includes(layer.type) ? t`${name} always prints` : layer.hidden ? t`Show ${name}` : t`Hide ${name}`} onClick={() => onToggle(layer.id, "hidden")}>
        {layer.hidden ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}</button>
      <button className="desk-button min-h-11 min-w-11" type="button" aria-label={t`Duplicate ${name}`} disabled={full} onClick={() => onDuplicate(layer.id)}><Copy size={16} aria-hidden="true" /></button>
      <button className="desk-button min-h-11 min-w-11" type="button" aria-label={t`Delete ${name}`} disabled={layers.length === 1 || layer.locked} onClick={() => onDelete(layer.id)}><Trash2 size={16} aria-hidden="true" /></button>
    </li>;
  })}</ol>;
}
