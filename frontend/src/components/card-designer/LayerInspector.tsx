// Properties of the selected layer. Geometry for every kind, then the kind's own settings.
import { t } from "@lingui/core/macro";
import type { Layer, Side } from "./cardTypes";
import { qrMinimum } from "./cardGeometry";
import { layerContrast, MINIMUM_RATIO } from "./contrast";
import { fieldsFor } from "./dataFields";
import { BARCODE_MIN_HEIGHT_MM, BARCODE_MIN_WIDTH_MM, layerName } from "./designDocument";
import { canonicalFamily } from "./fontLoader";
import { FontPicker } from "./FontPicker";
import { ColourInput, NumberInput, SelectInput, Toggle } from "./inspectorFields";

const TEXT_KINDS = new Set(["text", "data_field"]);

export function LayerInspector({ side, layer, designId, stock, assetColours, onChange, readOnly, answerFields }: {
  side: Side; layer: Layer; designId: number; stock: string; assetColours: Record<string, string>;
  answerFields?: { key: string; label: string }[];
  onChange: (patch: Partial<Layer>) => void; readOnly: boolean;
}) {
  const qr = layer.kind === "desk_qr" || layer.kind === "verify_qr";
  const barcode = layer.kind === "barcode";
  const barcodeMin = BARCODE_MIN_WIDTH_MM[layer.source === "desk" ? "desk" : "number"];
  const index = side.layers.findIndex((item) => item.id === layer.id);
  const contrast = layerContrast(side, index, assetColours);
  const disabled = readOnly || layer.locked;
  const minSize = qr ? qrMinimum(stock) : barcode ? barcodeMin : 0.5;
  return <div className="grid gap-4" aria-label={`${layerName(layer)} settings`} role="group">
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
      <NumberInput label={t`Height`} unit="mm" value={layer.h_mm} min={qr ? minSize : barcode ? BARCODE_MIN_HEIGHT_MM : 0.3}
        max={side.page_height_mm}
        disabled={disabled} onChange={(h_mm) => onChange(qr ? { w_mm: h_mm, h_mm } : { h_mm })} />
      <NumberInput label={t`Rotation`} unit="°" value={layer.rotation} min={0} max={359} step={qr || barcode ? 90 : 1}
        disabled={disabled}
        onChange={(value) => onChange({ rotation: qr || barcode ? Math.round(value / 90) * 90 % 360 : value })} />
      {!qr && !barcode ? <NumberInput label={t`Opacity`} unit="%" value={layer.opacity} min={0} max={100} step={5} disabled={disabled}
        onChange={(opacity) => onChange({ opacity })} /> : null}
    </div>
    {qr ? <p className="text-xs text-muted">{t`QR codes stay at least ${qrMinimum(stock)} mm, fully opaque and square-on so every phone can read them. `}{layer.kind === "desk_qr" ? t`The desk QR is scanned at the front desk; it is never shown on the public check page.`
        : t`The check QR opens the public page that says whether this card is valid.`}</p> : null}
    {barcode ? <div className="grid gap-2">
      <SelectInput label={t`Barcode carries`} value={layer.source === "desk" ? "desk" : "number"} disabled={disabled}
        options={[{ value: "number", label: t`The card number` }, { value: "desk", label: t`The desk code (USB scanners)` }]}
        onChange={(source) => onChange(source === "desk" ? { source, w_mm: Math.max(layer.w_mm, BARCODE_MIN_WIDTH_MM.desk) } : { source })} />
      <Toggle label={t`Print the code under the bars`} checked={layer.show_text !== false} disabled={disabled}
        onChange={(show_text) => onChange({ show_text })} />
      <p className="text-xs text-muted">{t`Code128, black on a white plate. It needs at least ${barcodeMin} × ${BARCODE_MIN_HEIGHT_MM} mm so a scanner reads it`}{layer.source === "desk" ? t`; the desk code is the same private code as the desk QR, for barcode scanners at the desk` : ""}.
        {barcodeMin > side.page_width_mm - 6 ? t` This card is too narrow for it: use a landscape or larger card.` : ""}</p>
    </div> : null}
    {layer.kind === "photo" ? <div className="grid gap-2">
      <SelectInput label={t`Photo look`} value={layer.filter ?? "none"} disabled={disabled}
        options={[{ value: "none", label: t`Original colours` }, { value: "grey", label: t`Black and white` },
          { value: "duotone", label: t`Duotone (two colours)` }]} onChange={(filter) => onChange({ filter })} />
      {layer.filter === "duotone" ? <div className="grid grid-cols-2 gap-2">
        <ColourInput label={t`Shadows`} value={layer.duotone_dark ?? "#142C2A"} disabled={disabled}
          onChange={(duotone_dark) => duotone_dark && onChange({ duotone_dark })} />
        <ColourInput label={t`Highlights`} value={layer.duotone_light ?? "#DFFF8F"} disabled={disabled}
          onChange={(duotone_light) => duotone_light && onChange({ duotone_light })} />
      </div> : null}
    </div> : null}
    {TEXT_KINDS.has(layer.kind) ? <TextSettings layer={layer} designId={designId} disabled={disabled} onChange={onChange}
      answerFields={answerFields} /> : null}
    {TEXT_KINDS.has(layer.kind) && contrast !== null && contrast < MINIMUM_RATIO
      ? <p role="status" className="rounded-control border border-warn bg-warn-soft p-2 text-sm text-warn-ink">
        {t`Hard to read: contrast ${contrast.toFixed(1)}:1 against what is behind it. Publishing needs at least ${MINIMUM_RATIO}:1.`}</p> : null}
    {layer.kind === "shape" || layer.kind === "band" ? <div className="grid gap-2">
      {layer.kind === "shape" ? <SelectInput label={t`Shape`} value={layer.shape === "ellipse" || layer.shape === "line" ? layer.shape : "rect"}
        disabled={disabled} options={[{ value: "rect", label: t`Rectangle` }, { value: "ellipse", label: t`Ellipse` }, { value: "line", label: t`Line` }]}
        onChange={(shape) => onChange({ shape })} /> : null}
      <ColourInput label={t`Fill`} value={layer.fill} allowNone={layer.kind === "shape"} disabled={disabled} onChange={(fill) => onChange({ fill })} />
      {layer.kind === "shape" ? <>
        <ColourInput label={t`Outline`} value={layer.stroke} allowNone disabled={disabled} onChange={(stroke) => onChange({ stroke })} />
        <NumberInput label={t`Outline width`} unit="mm" value={layer.stroke_mm ?? 0.3} min={0} max={5} step={0.1}
          disabled={disabled} onChange={(stroke_mm) => onChange({ stroke_mm })} />
      </> : null}
      <NumberInput label={t`Corner radius`} unit="mm" value={layer.radius_mm ?? 0} min={0} max={20} disabled={disabled}
        onChange={(radius_mm) => onChange({ radius_mm })} />
    </div> : null}
    {layer.kind === "photo" ? <SelectInput label={t`Photo shape`} value={(layer.shape ?? "rounded") as "rounded" | "circle" | "square"}
      disabled={disabled} options={[{ value: "rounded", label: t`Rounded` }, { value: "circle", label: t`Circle` }, { value: "square", label: t`Square` }]}
      onChange={(shape) => onChange({ shape })} /> : null}
    {layer.kind === "logo" ? <div className="grid gap-2">
      <SelectInput label={t`Logo`} value={layer.source ?? "space"} disabled={disabled} onChange={(source) => onChange({ source })}
        options={[{ value: "space", label: t`The space's logo` }, { value: "organisation", label: t`The organisation's logo` },
          { value: "event", label: t`The event's logo` }, { value: "symbol", label: t`Space Works symbol` }]} />
      <Toggle label={t`White tile behind the logo`} checked={Boolean(layer.tile)} disabled={disabled} onChange={(tile) => onChange({ tile })} />
    </div> : null}
    {layer.kind === "image" ? <SelectInput label={t`Fit`} value={layer.fit ?? "contain"} disabled={disabled}
      options={[{ value: "contain", label: t`Show the whole image` }, { value: "cover", label: t`Fill the box` }]}
      onChange={(fit) => onChange({ fit })} /> : null}
    {layer.kind === "perforation" ? <div className="grid gap-2">
      <SelectInput label={t`Direction`} value={layer.orientation ?? "vertical"} disabled={disabled}
        options={[{ value: "vertical", label: t`Vertical` }, { value: "horizontal", label: t`Horizontal` }]}
        onChange={(orientation) => onChange({ orientation })} />
      <ColourInput label={t`Colour`} value={layer.colour} disabled={disabled} onChange={(colour) => colour && onChange({ colour })} />
    </div> : null}
    <div className="flex flex-wrap gap-x-4">
      <Toggle label={t`Locked`} checked={layer.locked} disabled={readOnly} onChange={(locked) => onChange({ locked })} />
      <Toggle label={t`Hidden`} checked={layer.hidden} disabled={readOnly} onChange={(hidden) => onChange({ hidden })} />
    </div>
  </div>;
}

function TextSettings({ layer, designId, disabled, onChange, answerFields }: {
  layer: Layer; designId: number; disabled: boolean; onChange: (patch: Partial<Layer>) => void;
  answerFields?: { key: string; label: string }[];
}) {
  return <div className="grid gap-2">
    {layer.kind === "data_field"
      ? <SelectInput label={t`Data field`} value={layer.field ?? "name"} disabled={disabled}
        options={fieldsFor(answerFields).map((field) => ({ value: field.key, label: field.label }))}
        onChange={(field) => onChange({ field, text: `{{${field}}}` })} />
      : <label className="grid gap-1 text-xs font-semibold text-muted">
        <span>{t`Text`}</span>
        <textarea className="desk-input min-h-20" maxLength={500} value={layer.text ?? ""} disabled={disabled}
          onChange={(event) => onChange({ text: event.target.value })} />
        <span className="font-normal">{t`Insert a field with ${"{{name}}"}, ${"{{number}}"}, ${"{{valid_until}}"} and so on.`}</span>
      </label>}
    <div className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Font`}</span>
      <FontPicker designId={designId} family={canonicalFamily(layer.font_family ?? "Outfit")} weight={layer.font_weight ?? 400}
        disabled={disabled} onChange={(font_family, font_weight) => onChange({ font_family, font_weight })} />
    </div>
    <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Size`} unit="pt" value={layer.font_size_pt ?? 10} min={6} max={96} disabled={disabled}
        onChange={(font_size_pt) => onChange({ font_size_pt })} />
      <NumberInput label={t`Letter spacing`} unit="pt" value={layer.tracking_pt ?? 0} min={-2} max={10} step={0.1}
        disabled={disabled} onChange={(tracking_pt) => onChange({ tracking_pt })} />
      <SelectInput label={t`Align`} value={layer.align ?? "left"} disabled={disabled} onChange={(align) => onChange({ align })}
        options={[{ value: "left", label: t`Left` }, { value: "center", label: t`Centre` }, { value: "right", label: t`Right` }]} />
      <SelectInput label={t`Vertical`} value={layer.valign ?? "top"} disabled={disabled} onChange={(valign) => onChange({ valign })}
        options={[{ value: "top", label: t`Top` }, { value: "middle", label: t`Middle` }, { value: "bottom", label: t`Bottom` }]} />
    </div>
    <ColourInput label={t`Text colour`} value={layer.colour} disabled={disabled} onChange={(colour) => colour && onChange({ colour })} />
    <div className="flex flex-wrap gap-x-4">
      <Toggle label={t`Capitals`} checked={Boolean(layer.uppercase)} disabled={disabled} onChange={(uppercase) => onChange({ uppercase })} />
      <Toggle label={t`Shrink long text to fit`} checked={layer.shrink_to_fit !== false} disabled={disabled}
        onChange={(shrink_to_fit) => onChange({ shrink_to_fit })} />
    </div>
  </div>;
}
