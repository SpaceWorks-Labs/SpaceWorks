import { t } from "@lingui/core/macro";
import { Field } from "../../components/ui";
import { DISPLAY_PANELS, type AdminDisplay, type DisplayConfigInput, type DisplayLayout, type DisplayPanel, type DisplayPrivacy, type DisplayTheme } from "./api";
import { PanelOrderEditor } from "./PanelOrderEditor";

export const panelLabel = (panel: DisplayPanel): string => ({
  here_now: t`Here now`, calendar: t`Events calendar`, machines: t`Machines now`, announcement: t`Announcement`,
  public_stats: t`Public stats`, opening_hours: t`Opening hours`, inventory_highlights: t`Inventory highlights`, sponsors: t`Sponsors` })[panel];
export const layoutLabel = (layout: DisplayLayout): string =>
  ({ single: t`Single panel`, grid: t`Grid, all at once`, playlist: t`Rotating playlist` })[layout];
export const themeLabel = (theme: DisplayTheme): string =>
  ({ dark: t`Dark`, light: t`Light`, black: t`Solid black`, brand: t`Space brand`, space: t`Space default` })[theme];
export const privacyLabel = (privacy: DisplayPrivacy): string =>
  ({ profiles: t`People who opened their profile, by name; everyone else counted`, first_names: t`First names only`, counts: t`Counts only, no names` })[privacy];

export type Draft = { name: string; panels: DisplayPanel[]; rotation: string; announcement: string; layout: DisplayLayout;
  theme: DisplayTheme; privacy: DisplayPrivacy; refresh: string; slides: Partial<Record<DisplayPanel, string>> };
export const blank: Draft = { name: "", panels: ["here_now", "calendar", "machines"], rotation: "15", announcement: "", layout: "playlist",
  theme: "dark", privacy: "profiles", refresh: "30", slides: {} };

export const draftOf = (row: AdminDisplay): Draft => ({ name: row.name, panels: row.panels, rotation: String(row.rotation_seconds),
  announcement: row.announcement, layout: row.layout, theme: row.theme, privacy: row.privacy, refresh: String(row.refresh_seconds),
  slides: Object.fromEntries(Object.entries(row.slide_seconds).map(([k, v]) => [k, String(v)])) });

export function toInput(draft: Draft): DisplayConfigInput {
  const slides = Object.fromEntries(draft.panels.filter((p) => draft.slides[p]).map((p) => [p, Number(draft.slides[p])]));
  return { name: draft.name, panels: draft.panels, rotation_seconds: Number(draft.rotation), announcement: draft.announcement,
    layout: draft.layout, theme: draft.theme, privacy: draft.privacy, refresh_seconds: Number(draft.refresh), slide_seconds: slides };
}

const digits = (value: string) => value.replace(/\D/g, "");

function Choice<K extends string>({ label, value, options, text, onChange, hint }:
  { label: string; value: K; options: K[]; text: (k: K) => string; onChange: (k: K) => void; hint?: string }) {
  return <Field label={label} hint={hint}><select className="desk-input" value={value} onChange={(e) => onChange(e.target.value as K)}>
    {options.map((o) => <option key={o} value={o}>{text(o)}</option>)}</select></Field>;
}

/** Everything a Space Manager sets for one screen: sections and order, layout, theme, privacy, refresh. */
export function DisplayConfigFields({ draft, setDraft }: { draft: Draft; setDraft: (next: Draft) => void }) {
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  return <div className="grid gap-3 sm:grid-cols-2">
    <Field label={t`Screen name`}><input className="desk-input" maxLength={80} value={draft.name} onChange={(e) => set({ name: e.target.value })} /></Field>
    <Choice label={t`Layout`} value={draft.layout} options={["playlist", "single", "grid"]} text={layoutLabel} onChange={(layout) => set({ layout })} />
    <PanelOrderEditor legend={t`Sections, in order`} all={DISPLAY_PANELS} value={draft.panels} label={panelLabel} onChange={(panels) => set({ panels })} />
    <div className="grid content-start gap-3">
      <Choice label={t`Theme`} value={draft.theme} options={["dark", "light", "black", "brand", "space"]} text={themeLabel} onChange={(theme) => set({ theme })} />
      <Choice label={t`Who Here now shows`} value={draft.privacy} options={["profiles", "first_names", "counts"]} text={privacyLabel}
        hint={t`Never shows more than the public page does.`} onChange={(privacy) => set({ privacy })} />
      <Field label={t`Refresh data every (seconds)`} hint={t`Between 10 and 600.`}>
        <input className="desk-input" inputMode="numeric" value={draft.refresh} onChange={(e) => set({ refresh: digits(e.target.value) })} /></Field>
    </div>
    {draft.layout === "playlist" ? <fieldset className="grid gap-2 sm:col-span-2"><legend className="text-sm font-semibold text-ink">{t`Seconds per slide`}</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {draft.panels.map((panel) => <Field key={panel} label={panelLabel(panel)}>
          <input className="desk-input" inputMode="numeric" placeholder={draft.rotation} value={draft.slides[panel] ?? ""}
            onChange={(e) => set({ slides: { ...draft.slides, [panel]: digits(e.target.value) } })} /></Field>)}
      </div>
      <Field label={t`Default seconds per slide`} hint={t`Between 5 and 120. Used where a slide has no number.`}>
        <input className="desk-input" inputMode="numeric" value={draft.rotation} onChange={(e) => set({ rotation: digits(e.target.value) })} /></Field>
    </fieldset> : null}
    <Field label={t`Announcement`} hint={t`Shown by the Announcement section. Up to 280 characters.`} className="sm:col-span-2">
      <textarea className="desk-input" rows={3} maxLength={280} value={draft.announcement} onChange={(e) => set({ announcement: e.target.value })} /></Field>
  </div>;
}
