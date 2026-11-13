// Rich text settings: type the text, select a word, then style just that selection (font, weight, colour, size,
// capitals). Layer-wide spacing, line height, glyph stroke, shadow, highlight bar and underline follow.
import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";

import type { Layer, Span } from "./cardTypes";
import { fieldsFor } from "./dataFields";
import { MAX_SPANS } from "./designDocument";
import { InspectorSection } from "./InspectorSection";
import { ColourInput, NumberInput, SelectInput, Toggle } from "./inspectorFields";
import { ShadowControls } from "./StudioEffectControls";
import { StudioFontPicker } from "./StudioFontPicker";
import { nearestWeight, studioFont } from "./studioFonts";
import { applyToRange, retypeSpans, spansText, textStroke } from "./studioText";

type Change = (patch: Partial<Layer>) => void;

function SpanStyler({ layer, disabled, onChange }: { layer: Layer; disabled: boolean; onChange: Change }) {
  const area = useRef<HTMLTextAreaElement>(null);
  const [range, setRange] = useState<[number, number]>([0, 0]);
  const spans: Span[] = layer.spans?.length ? layer.spans : [{ text: layer.text ?? "" }];
  const text = spansText(spans);
  const selected = range[1] > range[0];
  const family = layer.font_family ?? "Outfit";
  const apply = (patch: Partial<Span>) => {
    const [start, end] = selected ? range : [0, text.length];
    const next = applyToRange(spans, start, end, patch);
    if (next.length <= MAX_SPANS) onChange({ spans: next, text: spansText(next) });
  };
  const at = (() => { let n = 0; return spans.find((span) => (n += span.text.length) > range[0]) ?? spans[0]; })();
  const grab = () => { const el = area.current; if (el) setRange([el.selectionStart, el.selectionEnd]); };
  return <div className="grid gap-2">
    <label className="grid gap-1 text-xs font-semibold text-muted">
      <span>{t`Text`}</span>
      <textarea ref={area} className="desk-input min-h-20" maxLength={500} value={text} disabled={disabled}
        onSelect={grab} onKeyUp={grab} onMouseUp={grab}
        onChange={(event) => onChange(layer.spans?.length
          ? { spans: retypeSpans(spans, event.target.value), text: event.target.value } : { text: event.target.value })} />
      <span className="font-normal">{t`Insert a field with ${"{{name}}"}, ${"{{number}}"} and so on. Select some words to style only them.`}</span>
    </label>
    <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
      <legend className="px-1 text-xs font-semibold text-muted">{selected ? t`Style the selected words` : t`Style all the text`}</legend>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button min-h-11 font-bold" onClick={() => apply({ font_weight: nearestWeight(at.font_family ?? family, 800) })}>{t`Bold`}</button>
        <button type="button" className="desk-button min-h-11 font-light" onClick={() => apply({ font_weight: nearestWeight(at.font_family ?? family, 300) })}>{t`Light`}</button>
        <button type="button" className="desk-button min-h-11 uppercase" onClick={() => apply({ uppercase: true })}>{t`Capitals`}</button>
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => onChange({ spans: null, text })}>{t`Clear styling`}</button>
      </div>
      <ColourInput label={t`Colour of the selection`} value={at.colour ?? layer.colour} onChange={(colour) => colour && apply({ colour })} />
      <SelectInput label={t`Size of the selection`} value={String(at.size_scale ?? 1)} onChange={(value) => apply({ size_scale: Number(value), size_pt: null })}
        options={[0.6, 0.8, 1, 1.25, 1.5, 2, 3].map((scale) => ({ value: String(scale), label: `${Math.round(scale * 100)}%` }))} />
      <details>
        <summary className="min-h-11 cursor-pointer py-3 text-xs font-semibold text-muted">{t`Font of the selection`}</summary>
        <StudioFontPicker family={at.font_family ?? family} weight={at.font_weight ?? layer.font_weight ?? 400}
          onChange={(font_family, font_weight) => apply({ font_family, font_weight })} />
      </details>
      {layer.spans && layer.spans.length > 1 ? <p className="text-xs text-muted">{t`${layer.spans.length} styled runs.`}</p> : null}
    </fieldset>
  </div>;
}

export function RichTextInspector({ layer, disabled, onChange, answerFields, fieldOptions }: {
  layer: Layer; disabled: boolean; onChange: Change; answerFields?: { key: string; label: string }[];
  /** Replaces the built-in data fields (certificates have their own tags). */
  fieldOptions?: { key: string; label: string }[];
}) {
  const stroke = textStroke(layer);
  const family = layer.font_family ?? "Outfit";
  return <div className="grid gap-3">
    {layer.kind === "data_field"
      ? <SelectInput label={t`Data field`} value={layer.field ?? "name"} disabled={disabled}
        options={(fieldOptions ?? fieldsFor(answerFields)).map((field) => ({ value: field.key, label: field.label }))}
        onChange={(field) => onChange({ field, text: `{{${field}}}`, spans: null })} />
      : <SpanStyler layer={layer} disabled={disabled} onChange={onChange} />}
    <div className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Font`}</span>
      <StudioFontPicker family={family} weight={layer.font_weight ?? 400} disabled={disabled}
        onChange={(font_family, font_weight) => onChange({ font_family, font_weight })} /></div>
    <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Size`} unit="pt" value={layer.font_size_pt ?? 10} min={6} max={200} disabled={disabled}
        onChange={(font_size_pt) => onChange({ font_size_pt })} />
      <NumberInput label={t`Letter spacing`} unit="pt" value={layer.tracking_pt ?? 0} min={-2} max={20} step={0.1}
        disabled={disabled} onChange={(tracking_pt) => onChange({ tracking_pt })} />
      <NumberInput label={t`Line height`} value={layer.line_height ?? 1.2} min={0.8} max={2.5} step={0.05} disabled={disabled}
        onChange={(line_height) => onChange({ line_height })} />
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
    <InspectorSection title={t`Effects`} defaultOpen={false}>
    <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
      <legend className="px-1 text-xs font-semibold text-muted">{t`Outline of the letters`}</legend>
      <Toggle label={t`Outline the letters`} checked={Boolean(stroke)} disabled={disabled}
        onChange={(on) => onChange({ stroke: on ? { colour: "#FFFFFF", width_pt: 1 } : null })} />
      {stroke ? <div className="grid grid-cols-2 gap-2">
        <ColourInput label={t`Colour`} value={stroke.colour} onChange={(colour) => colour && onChange({ stroke: { ...stroke, colour } })} />
        <NumberInput label={t`Width`} unit="pt" value={stroke.width_pt} min={0.1} max={8} step={0.1}
          onChange={(width_pt) => onChange({ stroke: { ...stroke, width_pt } })} />
      </div> : null}
    </fieldset>
    <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
      <legend className="px-1 text-xs font-semibold text-muted">{t`Highlight bar`}</legend>
      <Toggle label={t`Highlight each line`} checked={Boolean(layer.highlight)} disabled={disabled}
        onChange={(on) => onChange({ highlight: on ? { colour: "#DFFF8F", pad_x_mm: 1.5, pad_y_mm: 0.6, radius_mm: 0.8 } : null })} />
      {layer.highlight ? <div className="grid grid-cols-2 gap-2">
        <ColourInput label={t`Colour`} value={layer.highlight.colour} onChange={(colour) => colour && onChange({ highlight: { ...layer.highlight!, colour } })} />
        <NumberInput label={t`Side padding`} unit="mm" value={layer.highlight.pad_x_mm} min={0} max={10} step={0.1}
          onChange={(pad_x_mm) => onChange({ highlight: { ...layer.highlight!, pad_x_mm } })} />
        <NumberInput label={t`Top and bottom`} unit="mm" value={layer.highlight.pad_y_mm} min={0} max={10} step={0.1}
          onChange={(pad_y_mm) => onChange({ highlight: { ...layer.highlight!, pad_y_mm } })} />
        <NumberInput label={t`Corner radius`} unit="mm" value={layer.highlight.radius_mm} min={0} max={10} step={0.1}
          onChange={(radius_mm) => onChange({ highlight: { ...layer.highlight!, radius_mm } })} />
      </div> : null}
    </fieldset>
    <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
      <legend className="px-1 text-xs font-semibold text-muted">{t`Underline bar`}</legend>
      <Toggle label={t`Underline each line`} checked={Boolean(layer.underline)} disabled={disabled}
        onChange={(on) => onChange({ underline: on ? { colour: layer.colour ?? "#142C2A", thickness_pt: 1.5, offset_pt: 2 } : null })} />
      {layer.underline ? <div className="grid grid-cols-2 gap-2">
        <ColourInput label={t`Colour`} value={layer.underline.colour} onChange={(colour) => colour && onChange({ underline: { ...layer.underline!, colour } })} />
        <NumberInput label={t`Thickness`} unit="pt" value={layer.underline.thickness_pt} min={0.5} max={8} step={0.1}
          onChange={(thickness_pt) => onChange({ underline: { ...layer.underline!, thickness_pt } })} />
        <NumberInput label={t`Gap below the text`} unit="pt" value={layer.underline.offset_pt} min={0} max={12} step={0.5}
          onChange={(offset_pt) => onChange({ underline: { ...layer.underline!, offset_pt } })} />
      </div> : null}
    </fieldset>
    <ShadowControls shadow={layer.shadow ?? null} maxBlur={2} disabled={disabled} onChange={(shadow) => onChange({ shadow })} />
    </InspectorSection>
    {studioFont(family) ? null : <p className="text-xs text-muted">{t`Letter outline, highlight and underline work with every font.`}</p>}
  </div>;
}
