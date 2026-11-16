import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { PAGE_PRESETS, pagePreset, resizePage, type LayerDocument, type PagePreset } from "../layout";
import { CERTIFICATE_KINDS, SAMPLE_NAMES, type CertificateKind } from "./samples";

/** Page size: A4 and US Letter in both orientations, or a custom size from 100 to 420 mm. */
export function PageSizeFields({ document, onChange }: { document: LayerDocument; onChange: (value: LayerDocument) => void }) {
  const preset = pagePreset(document.page_width_mm, document.page_height_mm);
  const custom = (key: "page_width_mm" | "page_height_mm", value: number) => {
    if (!Number.isFinite(value) || value < 100 || value > 420) return;
    onChange(resizePage(document, key === "page_width_mm" ? value : document.page_width_mm, key === "page_height_mm" ? value : document.page_height_mm));
  };
  return <fieldset className="grid gap-3 sm:grid-cols-3">
    <legend className="mb-1 text-sm font-semibold text-ink">{t`Page`}</legend>
    <label className="grid gap-1 text-sm">{t`Paper size`}<select className="desk-input" value={preset} onChange={(event) => {
      const next = event.target.value as PagePreset;
      if (next !== "custom") onChange(resizePage(document, PAGE_PRESETS[next].size[0], PAGE_PRESETS[next].size[1]));
    }}>{Object.entries(PAGE_PRESETS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}
      <option value="custom">{t`Custom size`}</option></select></label>
    {(["page_width_mm", "page_height_mm"] as const).map((key) => <SideField key={key} label={key === "page_width_mm" ? t`Width (mm)` : t`Height (mm)`}
      value={document[key]} onCommit={(value) => custom(key, value)} />)}
  </fieldset>;
}

/** A page side typed freely and applied on blur or Enter, so partial numbers never fight the input. */
function SideField({ label, value, onCommit }: { label: string; value: number; onCommit: (value: number) => void }) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const number = Number(draft);
  const valid = Number.isFinite(number) && number >= 100 && number <= 420;
  return <label className="grid gap-1 text-sm">{label}<input type="number" className="desk-input" min={100} max={420} step={0.1}
    value={draft} aria-invalid={!valid} onChange={(event) => setDraft(event.target.value)}
    onBlur={() => valid ? onCommit(number) : setDraft(String(value))}
    onKeyDown={(event) => { if (event.key === "Enter" && valid) onCommit(number); }} />
    {!valid ? <span className="text-xs text-danger">{t`Use 100 to 420 mm.`}</span> : null}</label>;
}

/** Which certificate kind this design is for. A kind with no design of its own uses the default. */
export function KindPicker({ value, ownDesigns, usesDefault, onChange }: { value: CertificateKind | ""; ownDesigns: string[];
  usesDefault: boolean; onChange: (value: CertificateKind | "") => void }) {
  return <div className="grid gap-2">
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Design for`}<select className="desk-input font-normal" value={value} onChange={(event) => onChange(event.target.value as CertificateKind | "")}>
        <option value="">{t`Default design (every kind without its own)`}</option>
        {CERTIFICATE_KINDS.map((kind) => <option key={kind.value} value={kind.value}>
          {kind.label}{ownDesigns.includes(kind.value) ? t` (own design)` : ""}</option>)}
      </select></label>
    {value && usesDefault ? <p role="status" className="text-sm text-muted">
      {t`This kind uses the default design. Saving here gives `}{CERTIFICATE_KINDS.find((kind) => kind.value === value)?.label.toLowerCase()} {t` certificates their own design.`}</p> : null}
  </div>;
}

/** The sample recipient name the canvas and the PDF preview print. Never stored. */
export function SampleName({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <fieldset className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">{t`Sample name`}</legend>
    <div className="flex flex-wrap gap-2" role="group" aria-label={t`Sample name presets`}>
      {SAMPLE_NAMES.map((sample) => <button key={sample.key} type="button" className="desk-button min-h-11" aria-pressed={value === sample.value}
        onClick={() => onChange(sample.value)}>{sample.label}</button>)}
    </div>
    <label className="grid gap-1 text-sm">{t`Or type a name to try`}<input className="desk-input" maxLength={120} value={value}
      onChange={(event) => onChange(event.target.value)} /></label>
  </fieldset>;
}
