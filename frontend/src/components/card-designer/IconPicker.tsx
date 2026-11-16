// The icon library: a keyboard-reachable grid of the vendored icons (Add panel and the icon inspector).
import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { Layer } from "./cardTypes";
import { IconGlyph, iconLabel, ICON_KEYS } from "./IconLayerView";
import { ColourInput, Toggle } from "./inspectorFields";
import { SearchField } from "../ui/SearchField";

export function IconPicker({ value, onPick, disabled, label }: {
  value?: string; onPick: (icon: string) => void; disabled?: boolean; label: string;
}) {
  const [query, setQuery] = useState("");
  const shown = ICON_KEYS.filter((key) => !query.trim() || iconLabel(key).toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="grid gap-2">
    <label className="grid gap-1 text-xs font-semibold text-muted">
      <span>{label}</span>
      <SearchField className="desk-input min-h-11" value={query} placeholder={t`Search icons`} disabled={disabled}
        onChange={(event) => setQuery(event.target.value)} />
    </label>
    <div role="group" aria-label={label} className="grid grid-cols-5 gap-1">
      {shown.map((key) => <button key={key} type="button" disabled={disabled} aria-pressed={value === undefined ? undefined : value === key}
        aria-label={iconLabel(key)} title={iconLabel(key)} onClick={() => onPick(key)}
        className={`grid min-h-11 min-w-11 place-items-center rounded-control border p-2 focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-40 ${value === key ? "border-accent-ink bg-accent-soft" : "border-line bg-panel hover:border-accent-ink"}`}>
        <span className="h-6 w-6"><IconGlyph icon={key} colour="currentColor" /></span>
      </button>)}
    </div>
    {shown.length ? null : <p className="text-xs text-muted">{t`No icon matches that search.`}</p>}
  </div>;
}

export function IconInspector({ layer, disabled, onChange }: {
  layer: Layer; disabled: boolean; onChange: (patch: Partial<Layer>) => void;
}) {
  return <div className="grid gap-3">
    <IconPicker label={t`Icon`} value={layer.icon} disabled={disabled} onPick={(icon) => onChange({ icon })} />
    <ColourInput label={t`Colour`} value={layer.colour} disabled={disabled} onChange={(colour) => colour && onChange({ colour })} />
    <Toggle label={t`Mirror`} checked={Boolean(layer.flip_x)} disabled={disabled} onChange={(flip_x) => onChange({ flip_x })} />
  </div>;
}
