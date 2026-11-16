// The badge designer's settings panels, as in SpaceWorks-Events: Style (template), Colour, Paper and Text.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Section, CommitNumber, SwatchGroup, SwitchLine } from "./badgeControls";
import { layoutForPaper, type BadgeTemplate, type Flags } from "./badgeGeometry";
import { presetLabels, templateOptions, colourLabels } from "./badgeLabels";
import { ACCENT_KEYS, BACKGROUND_KEYS, TEXT_KEYS, TEXT_LIMITS, type BadgeSettings } from "./badgeNormalize";
import { BRAND, colourOf, resolvePalette } from "./badgePalette";

const TEAM_TAG = "{{team}}";
export type Update =(patch: Partial<BadgeSettings>, record?: boolean) => void;
export type Preset = { id: string; width_mm: number; height_mm: number };

export function StyleSection({ settings, flags, update }: { settings: BadgeSettings; flags: Partial<Flags>; update: Update }) {
  return <Section title={t`Style`}>
    <div role="radiogroup" aria-label={t`Badge style`} className="grid grid-cols-3 gap-2">
      {templateOptions().map((option) => {
        const active = settings.template === option.key;
        return <button key={option.key} type="button" role="radio" aria-checked={active} title={option.hint}
          onClick={() => update({ template: option.key, ...layoutForPaper(option.key, settings.widthMm, settings.heightMm, flags) })}
          className={`flex min-h-11 flex-col items-center gap-1.5 rounded-control border bg-panel p-2 text-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${active ? "border-outline shadow-[inset_0_0_0_1px_var(--color-outline)]" : "border-line hover:bg-surface"}`}>
          <TemplateThumb template={option.key} />
          <span className="text-xs font-semibold leading-tight text-ink">{option.label}</span>
        </button>;
      })}
    </div>
    <p className="text-xs text-muted">{t`Changing style resets positions.`}</p>
  </Section>;
}

/** A tiny drawing of each template: frame, band or bare page, the big name bar and the QR corner. */
function TemplateThumb({ template }: { template: BadgeTemplate }) {
  const bar = (left: number, top: number, width: number, height: number, colour: string) =>
    <span className="absolute block" style={{ left, top, width, height, background: colour }} />;
  return <span aria-hidden="true" className="relative block h-[52px] w-[38px] overflow-hidden bg-white outline outline-1 outline-line">
    {template === "classic" ? <>
      <span className="absolute inset-[2px] rounded-[1.5px] border" style={{ borderColor: BRAND.teal }} />
      {bar(6, 6, 9, 1.5, BRAND.ink)}{bar(6, 9, 18, 2.5, BRAND.ink)}{bar(6, 13.5, 20, 1, BRAND.teal)}
      {bar(6, 18, 24, 5, BRAND.ink)}{bar(6, 25, 15, 1.5, BRAND.ink)}
    </> : null}
    {template === "bold" ? <>
      <span className="absolute inset-x-[2px] top-[2px] block h-[12px] rounded-[1.5px]" style={{ background: BRAND.teal }} />
      {bar(5, 5, 8, 1.5, BRAND.cream)}{bar(5, 8.5, 18, 2.5, BRAND.cream)}{bar(5, 17, 26, 5, BRAND.ink)}{bar(5, 24, 15, 1.5, BRAND.ink)}
    </> : null}
    {template === "minimal" ? <>{bar(5, 5, 11, 1.5, BRAND.ink)}{bar(5, 19, 26, 5, BRAND.ink)}{bar(5, 26, 14, 1.5, BRAND.ink)}</> : null}
    <span className="absolute bottom-[5px] right-[5px] block border-[1.5px] border-dotted"
      style={{ borderColor: BRAND.ink, width: template === "minimal" ? 9 : 11, height: template === "minimal" ? 9 : 11 }} />
  </span>;
}

export function ColourSection({ settings, update }: { settings: BadgeSettings; update: Update }) {
  const palette = resolvePalette(settings);
  const swatch = (key: string) => (key === "auto" ? null : colourOf(key));
  const names = colourLabels();
  const autoName = palette.text === BRAND.ink ? names.ink : palette.text === BRAND.cream ? names.cream : names.white;
  return <Section title={t`Colour`}>
    <div role="radiogroup" aria-label={t`Colour mode`} className="inline-flex w-fit gap-1 rounded-control border border-line bg-surface p-1">
      {([["colour", t`Colour`], ["mono", t`Black and white`]] as const).map(([value, label]) =>
        <button key={value} type="button" role="radio" aria-checked={settings.colorMode === value} onClick={() => update({ colorMode: value })}
          className={`min-h-11 rounded-control border px-3 text-sm font-semibold ${settings.colorMode === value ? "border-outline bg-panel text-ink" : "border-transparent text-muted hover:text-ink"}`}>
          {label}</button>)}
    </div>
    {settings.colorMode === "mono"
      ? <p className="text-xs text-muted">{t`Print economy: black on white only, for laser and thermal printers. Logos and photos print in grey.`}</p>
      : <>
        <SwatchGroup label={t`Card`} value={settings.backgroundColor} options={BACKGROUND_KEYS} colourOf={swatch}
          onChange={(backgroundColor) => update({ backgroundColor })} />
        <SwatchGroup label={settings.template === "bold" ? t`Band and accents` : t`Frame and accents`} value={settings.accentColor}
          options={ACCENT_KEYS} colourOf={swatch} onChange={(accentColor) => update({ accentColor })} />
        <SwatchGroup label={t`Text`} value={settings.textColor} options={TEXT_KEYS} colourOf={swatch} onChange={(textColor) => update({ textColor })} />
        {palette.textAdjusted ? <p role="status" className="rounded-control border border-line bg-surface p-2 text-xs text-warn-ink">
          {t`That text colour doesn't have enough contrast on this card, so text prints in ${autoName}.`}</p> : null}
        <p className="text-xs text-muted">{t`Text always keeps a 4.5:1 contrast with what it sits on. Event accent: ${BRAND.teal}.`}</p>
      </>}
  </Section>;
}

const close = (a: number, b: number) => Math.abs(a - b) < 0.6;
export function matchPreset(presets: Preset[], width: number, height: number) {
  return presets.find((preset) => (close(preset.width_mm, width) && close(preset.height_mm, height))
    || (close(preset.width_mm, height) && close(preset.height_mm, width))) ?? null;
}

export function PaperSection({ settings, presets, onPaper, update }: { settings: BadgeSettings; presets: Preset[];
  onPaper: (width: number, height: number) => void; update: Update }) {
  const match = matchPreset(presets, settings.widthMm, settings.heightMm);
  const [custom, setCustom] = useState(!match);
  const labels = presetLabels();
  const landscape = settings.widthMm > settings.heightMm;
  const choose = (preset: Preset) => {
    setCustom(false);
    const turned = landscape !== preset.width_mm > preset.height_mm;
    onPaper(turned ? preset.height_mm : preset.width_mm, turned ? preset.width_mm : preset.height_mm);
  };
  return <Section title={t`Paper`}>
    <div role="radiogroup" aria-label={t`Badge stock`} className="flex flex-wrap gap-1.5">
      {presets.map((preset) => {
        const active = !custom && match?.id === preset.id;
        return <button key={preset.id} type="button" role="radio" aria-checked={active} title={labels[preset.id]?.detail}
          onClick={() => choose(preset)}
          className={`min-h-11 rounded-control border px-3 text-sm font-semibold ${active ? "border-outline bg-surface text-ink shadow-[inset_0_0_0_1px_var(--color-outline)]" : "border-line text-muted hover:text-ink"}`}>
          {labels[preset.id]?.label ?? preset.id}</button>;
      })}
      <button type="button" role="radio" aria-checked={custom} onClick={() => setCustom(true)}
        className={`min-h-11 rounded-control border px-3 text-sm font-semibold ${custom ? "border-outline bg-surface text-ink shadow-[inset_0_0_0_1px_var(--color-outline)]" : "border-line text-muted hover:text-ink"}`}>
        {t`Custom`}</button>
    </div>
    <p className="text-xs text-muted">{custom ? t`Enter your stock's size. Positions keep where they are.` : match ? labels[match.id]?.detail : null}
      {" "}{t`${settings.widthMm} × ${settings.heightMm} mm, ${landscape ? t`landscape` : t`portrait`}.`}</p>
    {custom ? <div className="grid grid-cols-2 gap-2">
      <CommitNumber label={t`Width (mm)`} min={40} max={300} step={0.1} value={settings.widthMm} onCommit={(widthMm) => update({ widthMm })} />
      <CommitNumber label={t`Height (mm)`} min={40} max={300} step={0.1} value={settings.heightMm} onCommit={(heightMm) => update({ heightMm })} />
    </div> : null}
    <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => onPaper(settings.heightMm, settings.widthMm)}>
      {t`Turn to ${landscape ? t`portrait` : t`landscape`}`}</button>
  </Section>;
}

export function TextSection({ settings, update }: { settings: BadgeSettings; update: Update }) {
  const input = (key: keyof typeof TEXT_LIMITS, label: string, disabled = false) =>
    <input aria-label={label} className="desk-input min-h-11 w-full" maxLength={TEXT_LIMITS[key]} value={settings[key]}
      disabled={disabled} onChange={(event) => update({ [key]: event.target.value })} />;
  return <Section title={t`Text`}>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Heading`}</span>{input("heading", t`Heading`)}</label>
    <SwitchLine label={t`Badge label`} checked={settings.showBadgeLabel} onChange={(showBadgeLabel) => update({ showBadgeLabel })} />
    {input("badgeLabel", t`Badge label text`, !settings.showBadgeLabel)}
    <SwitchLine label={t`Footer`} checked={settings.showFooter} onChange={(showFooter) => update({ showFooter })} />
    {input("footerText", t`Footer text`, !settings.showFooter)}
    <p className="text-xs text-muted">{t`Type ${TEAM_TAG} in any of these to print the attendee's team name.`}</p>
  </Section>;
}
