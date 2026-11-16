import { t } from "@lingui/core/macro";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { colourPresets } from "../../lib/colourPresets";
import { AudienceTabs } from "./colours/AudienceTabs";
import { ColourField } from "./colours/ColourField";
import { ContrastPanel } from "./colours/ContrastPanel";
import { ModeField } from "./colours/ModeField";
import { useColourDraft } from "./colours/useColourDraft";
import type { Makerspace } from "./StaffPanels";

type Props = { makerspace: Makerspace; settings?: Makerspace; loading: boolean };

export function MakerspaceThemeSettings({ makerspace, settings, loading }: Props) {
  const { draft, setDraft, theme, report, blocked, dirty, mutation, save, undoSave, canUndo, discard } = useColourDraft(makerspace, settings);
  const busy = loading || mutation.isPending;
  const isDefault = !draft.primary && !draft.accent;
  return <section aria-labelledby="space-colours" className="@container py-5">
    <h3 id="space-colours" className="title-section">{t`Colours`}</h3>
    <p className="mt-1 text-sm text-muted">{t`Two colours, shown on the screens each audience sees. Preview them in light and solid-black dark before saving.`}</p>
    <form className="mt-4 grid gap-6 @4xl:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]" onSubmit={(event) => { event.preventDefault(); if (!loading) save(); }}>
      <div className="grid content-start gap-4 @4xl:sticky @4xl:top-4 @4xl:self-start">
        <ColourField label={t`Primary fill`} value={draft.primary} placeholder="#006e63" disabled={busy} invalid={report.errors.some((e) => e.startsWith("primary"))}
          helper={t`Buttons and filled areas. Leave blank for Maker Teal.`} onChange={(primary) => setDraft({ ...draft, primary })} />
        <ColourField label={t`Link colour seed`} value={draft.accent} placeholder={t`Same as primary`} disabled={busy} invalid={report.errors.some((e) => e.startsWith("accent"))}
          helper={t`Links, outlines and the accent on receipts. Blank follows the primary fill.`} onChange={(accent) => setDraft({ ...draft, accent })} />
        <fieldset className="grid gap-2" disabled={busy}>
          <legend className="text-sm font-semibold">{t`Presets`}</legend>
          <div className="flex flex-wrap gap-2">{colourPresets().map((preset) => <button key={preset.id} type="button" className="desk-button" aria-pressed={draft.primary === preset.primary && draft.accent === preset.accent}
            onClick={() => setDraft({ ...draft, primary: preset.primary, accent: preset.accent })}>
            <span aria-hidden="true" className="mr-2 inline-block h-4 w-4 rounded-full border border-outline" style={{ backgroundColor: preset.primary || "rgb(0 110 99)" }} />{preset.name}</button>)}</div>
          <div><button type="button" className="desk-button-ghost" disabled={isDefault} onClick={() => setDraft({ ...draft, primary: "", accent: "" })}>{t`Reset to Space Works default`}</button></div>
        </fieldset>
        <ModeField value={draft.mode} disabled={busy} onChange={(mode) => setDraft({ ...draft, mode })} />
        <ContrastPanel theme={theme} pairs={report.pairs} errors={report.errors} valid={report.valid} onFix={(key, value) => setDraft({ ...draft, [key === "primary_color" ? "primary" : "accent"]: value })} />
        <div aria-live="polite">
          {mutation.error ? <p className="text-sm text-danger">{mutation.error.message}</p> : null}
          {mutation.isSuccess && !dirty ? <p className="text-sm text-success-ink">{t`Colours saved.`}</p> : null}
          {canUndo ? <button type="button" className="desk-button-ghost" disabled={mutation.isPending} onClick={undoSave}>{t`Undo last save`}</button> : null}
        </div>
      </div>
      <AudienceTabs theme={theme} />
      <div className="@4xl:col-span-2"><SettingsEditorActions dirty={dirty} onDiscard={discard} pending={mutation.isPending} disabled={!settings || busy || !dirty || blocked} /></div>
    </form>
  </section>;
}
