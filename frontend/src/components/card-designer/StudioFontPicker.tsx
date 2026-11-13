// The studio font picker: only the allow-list (free Gilroy Light/ExtraBold plus the vendored OFL faces).
// Old documents may hold another family; it stays valid and is shown as "Other" until changed.
import { t } from "@lingui/core/macro";
import { useEffect } from "react";

import { canonicalFamily, cssFamily } from "./fontLoader";
import { loadStudioFont, nearestWeight, STUDIO_FONTS, studioFont } from "./studioFonts";

export function StudioFontPicker({ family, weight, onChange, disabled }: {
  family: string; weight: number; onChange: (family: string, weight: number) => void; disabled?: boolean;
}) {
  const current = canonicalFamily(family);
  const font = studioFont(current);
  useEffect(() => { STUDIO_FONTS.forEach((item) => void loadStudioFont(item.family)); }, []);
  return <div className="grid gap-2">
    <ul className="grid gap-1" aria-label={t`Fonts`}>
      {STUDIO_FONTS.map((item) => <li key={item.family}>
        <button type="button" disabled={disabled} aria-pressed={item.family === current}
          className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-control border px-3 text-left text-base focus-visible:outline-2 focus-visible:outline-focus ${item.family === current ? "border-accent-ink bg-accent-soft" : "border-line"} text-ink`}
          style={{ fontFamily: `${cssFamily(item.family)}, sans-serif`, fontWeight: item.weights[item.weights.length > 2 ? 2 : 0] }}
          onClick={() => onChange(item.family, nearestWeight(item.family, weight))}>
          <span className="truncate">{item.label}</span>
        </button>
      </li>)}
    </ul>
    {!font ? <p className="text-xs text-muted">{t`This design uses another font (${current}). Pick one above to switch.`}</p> : null}
    <label className="grid gap-1 text-xs font-semibold text-muted">
      <span>{t`Weight`}</span>
      <select className="desk-input min-h-11" value={weight} disabled={disabled || !font || font.weights.length < 2}
        onChange={(event) => onChange(current, Number(event.target.value))}>
        {(font?.weights ?? [weight]).map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </label>
  </div>;
}
