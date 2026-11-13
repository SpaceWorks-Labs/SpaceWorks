import { t } from "@lingui/core/macro";
export const ACCENT_PRESETS = {
  maker_teal: { label: t`Maker Teal`, background: "#006E63", foreground: "#FFF4E8" },
  workshop_orange: { label: t`Workshop Orange`, background: "#FF7447", foreground: "#142C2A" },
  citron: { label: t`Citron`, background: "#DFFF8F", foreground: "#142C2A" },
  sky_blue: { label: t`Sky Blue`, background: "#B5CDFF", foreground: "#142C2A" },
  warm_yellow: { label: t`Warm Yellow`, background: "#FFD447", foreground: "#142C2A" },
} as const;
export type AccentPreset = keyof typeof ACCENT_PRESETS;
export function AccentPresetPicker({ value, onChange }: { value: AccentPreset | null; onChange: (preset: AccentPreset | null) => void }) {
  return <fieldset className="grid gap-3"><legend className="mb-2 text-sm font-semibold">{t`Event accent`}</legend><p className="text-sm text-muted">{t`Choose a Space Works palette preset for public highlights. Controls and status colours keep the shared theme.`}</p>
    <div className="flex flex-wrap gap-3"><label className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-panel px-3"><input type="radio" name="event-accent" checked={value === null} onChange={() => onChange(null)} />{t`Inherit`}</label>{Object.entries(ACCENT_PRESETS).map(([key, preset]) => <label key={key} className="flex min-h-11 items-center gap-2 rounded-xl border border-line px-3" style={{ backgroundColor: preset.background, color: preset.foreground }}><input type="radio" name="event-accent" checked={value === key} onChange={() => onChange(key as AccentPreset)} />{preset.label}</label>)}</div>
  </fieldset>;
}
