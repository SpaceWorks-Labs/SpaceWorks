import { t } from "@lingui/core/macro";
import type { Look } from "./useColourDraft";

/** The space's default theme (theme_config.mode). A visitor's own toggle still wins on public pages. */
export function ModeField({ value, disabled, onChange }: { value: Look; disabled?: boolean; onChange: (value: Look) => void }) {
  const options: [Look, string][] = [["light", t`Light`], ["dark", t`Solid black`], ["system", t`Follow the visitor's device`]];
  return <fieldset className="grid gap-1 text-sm" disabled={disabled}>
    <legend className="font-semibold">{t`Default look for visitors and screens`}</legend>
    <div className="flex flex-wrap gap-x-4 gap-y-1">{options.map(([key, label]) => <label key={key} className="flex min-h-11 items-center gap-2">
      <input type="radio" name="space-default-look" checked={value === key} onChange={() => onChange(key)} />{label}</label>)}</div>
    <p className="text-xs text-muted">{t`Used by public pages and display screens until a visitor picks their own, and by displays unless their settings choose a theme.`}</p>
  </fieldset>;
}
