// Drop-in elements. An image layer is added once its upload finishes (it cannot save empty).
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Award, Barcode, Image, Minus, QrCode, ScanLine, Shapes, Square, Type, UserRound, Variable } from "lucide-react";

import type { CardDomain, Layer, LayerKind, Side } from "./cardTypes";
import { fieldsFor } from "./dataFields";
import { MAX_LAYERS, newLayer } from "./designDocument";
import { UploadButton } from "./BackgroundPicker";

const ITEMS: { kind: LayerKind; label: string; icon: typeof Type }[] = [
  { kind: "text", label: t`Text`, icon: Type }, { kind: "data_field", label: t`Data field`, icon: Variable },
  { kind: "photo", label: t`Photo`, icon: UserRound }, { kind: "logo", label: t`Logo`, icon: Award },
  { kind: "verify_qr", label: t`Check QR`, icon: QrCode }, { kind: "desk_qr", label: t`Desk QR`, icon: ScanLine },
  { kind: "barcode", label: t`Barcode`, icon: Barcode },
  { kind: "shape", label: t`Shape`, icon: Shapes }, { kind: "band", label: t`Band`, icon: Square },
  { kind: "perforation", label: t`Perforation`, icon: Minus },
];

export function AddLayerMenu({ side, stock, domain, designId, onAdd, onAssetColour, readOnly, answerFields }: {
  side: Side; stock: string; domain: CardDomain; designId: number; onAdd: (layer: Layer) => void;
  answerFields?: { key: string; label: string }[];
  onAssetColour: (assetId: string, colour: string) => void; readOnly: boolean;
}) {
  const [field, setField] = useState("name");
  const full = side.layers.length >= MAX_LAYERS;
  if (readOnly) return null;
  // A ticket has exactly one QR, its check-in code (the desk-QR slot); it has no public check page.
  const items = ITEMS.filter((item) => !(domain === "event_ticket" && item.kind === "verify_qr"))
    .map((item) => (domain === "event_ticket" && item.kind === "desk_qr" ? { ...item, label: t`Check-in QR` } : item));
  return <div className="grid gap-3">
    {full ? <p className="text-sm text-muted">{t`A side holds at most ${MAX_LAYERS} layers.`}</p> : null}
    <div className="grid grid-cols-3 gap-2">
      {items.map(({ kind, label, icon: Icon }) => <button key={kind} type="button" disabled={full}
        className="grid min-h-16 place-items-center gap-1 rounded-control border border-line bg-panel px-2 py-2 text-xs font-semibold text-ink hover:border-accent-ink focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-40"
        onClick={() => onAdd(newLayer(kind, side, stock, kind === "data_field" ? { field, text: `{{${field}}}` } : {}))}>
        <Icon size={18} aria-hidden="true" />{label}
      </button>)}
    </div>
    <label className="grid gap-1 text-xs font-semibold text-muted">
      <span>{t`Field for a new data-field layer`}</span>
      <select className="desk-input min-h-11" value={field} onChange={(event) => setField(event.target.value)}>
        {fieldsFor(answerFields).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
      </select>
    </label>
    <div className="grid gap-1">
      <span className="flex items-center gap-1 text-xs font-semibold text-muted"><Image size={14} aria-hidden="true" />{t`Image layer`}</span>
      <UploadButton designId={designId} kind="image" label={t`Upload an image`} disabled={full}
        onUploaded={(asset_id, mean) => { onAssetColour(asset_id, mean); onAdd(newLayer("image", side, stock, { asset_id })); }} />
    </div>
  </div>;
}
