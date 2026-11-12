// Properties of the selected layer. Geometry for every kind, then the kind's own settings.
import { t } from "@lingui/core/macro";
import type { Layer, Side } from "./cardTypes";
import { qrMinimum } from "./cardGeometry";
import { layerContrast, MINIMUM_RATIO } from "./contrast";
import { barcodeMinimum, symbologyOf } from "./barcodes";
import { BarcodeInspector } from "./BarcodeInspector";
import { layerName } from "./designDocument";
import { CertificatePieceInspector, ImageInspector, PhotoInspector, ShapeInspector } from "./MediaInspectors";
import { IconInspector } from "./IconPicker";
import { InspectorSection } from "./InspectorSection";
import { RichTextInspector } from "./RichTextInspector";
import { ColourInput, NumberInput, SelectInput, Toggle } from "./inspectorFields";

const TEXT_KINDS = new Set(["text", "data_field"]);
const CERTIFICATE_KINDS = new Set(["signature", "signature_row", "seal", "certificate_id"]);

export function LayerInspector({ side, layer, stock, assetColours, onChange, readOnly, answerFields, fieldOptions }: {
  side: Side; layer: Layer; designId: number; stock: string; assetColours: Record<string, string>;
  answerFields?: { key: string; label: string }[]; fieldOptions?: { key: string; label: string }[];
  onChange: (patch: Partial<Layer>) => void; readOnly: boolean;
}) {
  const qr = layer.kind === "desk_qr" || layer.kind === "verify_qr";
  const barcode = layer.kind === "barcode";
  const barcodeMin = barcodeMinimum(symbologyOf(layer), layer.source);
  const index = side.layers.findIndex((item) => item.id === layer.id);
  const contrast = layerContrast(side, index, assetColours);
  const disabled = readOnly || layer.locked;
  const minSize = qr ? qrMinimum(stock) : barcode ? barcodeMin.w : 0.5;
  const kindTitle = TEXT_KINDS.has(layer.kind) ? t`Text` : layer.kind === "photo" ? t`Photo` : layer.kind === "image" ? t`Image`
    : layer.kind === "shape" || layer.kind === "band" ? t`Shape` : layer.kind === "icon" ? t`Icon` : t`Settings`;
  return <div className="grid gap-1" aria-label={`${layerName(layer)} settings`} role="group">
    <InspectorSection title={t`Position and size`}>
    <label className="grid gap-1 text-xs font-semibold text-muted">
      <span>{t`Layer name`}</span>
      <input className="desk-input min-h-11" maxLength={40} value={layer.name} placeholder={layerName(layer)}
        disabled={readOnly} onChange={(event) => onChange({ name: event.target.value })} />
    </label>
    <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Left`} unit="mm" value={layer.x_mm} min={-side.page_width_mm} max={side.page_width_mm}
        disabled={disabled} onChange={(x_mm) => onChange({ x_mm })} />
      <NumberInput label={t`Top`} unit="mm" value={layer.y_mm} min={-side.page_height_mm} max={side.page_height_mm}
        disabled={disabled} onChange={(y_mm) => onChange({ y_mm })} />
      <NumberInput label={t`Width`} unit="mm" value={layer.w_mm} min={minSize} max={side.page_width_mm} disabled={disabled}
        onChange={(w_mm) => onChange(qr ? { w_mm, h_mm: w_mm } : { w_mm })} />
      <NumberInput label={t`Height`} unit="mm" value={layer.h_mm} min={qr ? minSize : barcode ? barcodeMin.h : 0.3}
        max={side.page_height_mm}
        disabled={disabled} onChange={(h_mm) => onChange(qr ? { w_mm: h_mm, h_mm } : { h_mm })} />
      <NumberInput label={t`Rotation`} unit="°" value={layer.rotation} min={0} max={359} step={qr || barcode ? 90 : 1}
        disabled={disabled}
        onChange={(value) => onChange({ rotation: qr || barcode ? Math.round(value / 90) * 90 % 360 : value })} />
      {!qr && !barcode ? <NumberInput label={t`Opacity`} unit="%" value={layer.opacity} min={0} max={100} step={5} disabled={disabled}
        onChange={(opacity) => onChange({ opacity })} /> : null}
    </div>
    </InspectorSection>
    <InspectorSection title={kindTitle}>
    {qr ? <p className="text-xs text-muted">{t`QR codes stay at least ${qrMinimum(stock)} mm, fully opaque and square-on so every phone can read them. `}{layer.kind === "desk_qr" ? t`The desk QR is scanned at the front desk; it is never shown on the public check page.`
        : t`The check QR opens the public page that says whether this card is valid.`}</p> : null}
    {barcode ? <BarcodeInspector layer={layer} side={side} disabled={disabled} onChange={onChange} /> : null}
    {layer.kind === "photo" ? <PhotoInspector layer={layer} disabled={disabled} onChange={onChange} /> : null}
    {TEXT_KINDS.has(layer.kind) ? <RichTextInspector layer={layer} disabled={disabled} onChange={onChange} answerFields={answerFields} fieldOptions={fieldOptions} /> : null}
    {TEXT_KINDS.has(layer.kind) && contrast !== null && contrast < MINIMUM_RATIO
      ? <p role="status" className="rounded-control border border-warn bg-warn-soft p-2 text-sm text-warn-ink">
        {t`Hard to read: contrast ${contrast.toFixed(1)}:1 against what is behind it. Publishing needs at least ${MINIMUM_RATIO}:1.`}</p> : null}
    {layer.kind === "shape" ? <ShapeInspector layer={layer} disabled={disabled} onChange={onChange} /> : null}
    {layer.kind === "band" ? <div className="grid gap-2">
      <ColourInput label={t`Fill`} value={layer.fill} disabled={disabled} onChange={(fill) => onChange({ fill })} />
      <NumberInput label={t`Corner radius`} unit="mm" value={layer.radius_mm ?? 0} min={0} max={20} disabled={disabled}
        onChange={(radius_mm) => onChange({ radius_mm })} />
    </div> : null}
    {layer.kind === "logo" ? <div className="grid gap-2">
      <SelectInput label={t`Logo`} value={layer.source ?? "space"} disabled={disabled} onChange={(source) => onChange({ source })}
        options={[{ value: "space", label: t`The space's logo` }, { value: "organisation", label: t`The organisation's logo` },
          { value: "event", label: t`The event's logo` }, { value: "symbol", label: t`Space Works symbol` }]} />
      <Toggle label={t`White tile behind the logo`} checked={Boolean(layer.tile)} disabled={disabled} onChange={(tile) => onChange({ tile })} />
    </div> : null}
    {layer.kind === "image" ? <ImageInspector layer={layer} disabled={disabled} onChange={onChange} /> : null}
    {layer.kind === "icon" ? <IconInspector layer={layer} disabled={disabled} onChange={onChange} /> : null}
    {CERTIFICATE_KINDS.has(layer.kind) ? <CertificatePieceInspector layer={layer} disabled={disabled} onChange={onChange} /> : null}
    {layer.kind === "perforation" ? <div className="grid gap-2">
      <SelectInput label={t`Direction`} value={layer.orientation ?? "vertical"} disabled={disabled}
        options={[{ value: "vertical", label: t`Vertical` }, { value: "horizontal", label: t`Horizontal` }]}
        onChange={(orientation) => onChange({ orientation })} />
      <ColourInput label={t`Colour`} value={layer.colour} disabled={disabled} onChange={(colour) => colour && onChange({ colour })} />
    </div> : null}
    </InspectorSection>
    <InspectorSection title={t`Arrange`} defaultOpen={false}>
    <div className="flex flex-wrap gap-x-4">
      <Toggle label={t`Locked`} checked={layer.locked} disabled={readOnly} onChange={(locked) => onChange({ locked })} />
      <Toggle label={t`Hidden`} checked={layer.hidden} disabled={readOnly} onChange={(hidden) => onChange({ hidden })} />
    </div>
    </InspectorSection>
  </div>;
}
