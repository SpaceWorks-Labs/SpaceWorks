import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { ActionControl, Callout, Field, SettingsRow, StatusPill } from "../../../components/ui";
import { SectionOrderList } from "./SectionOrderList";
import { usePublicStatsSettings, useSavePublicStatsSettings, type PublicStatsSettings } from "./api";

/**
 * Settings › Public stats (#170): page on/off, the sections and their order, the one fixed
 * period, up to four headline numbers and the TV mode. Space Manager only (the settings
 * authority refuses everyone else); other staff see it read-only.
 */
export function PublicStatsSettingsPanel({ makerspaceId, slug }: { makerspaceId: number; slug: string }) {
  const query = usePublicStatsSettings(makerspaceId);
  const save = useSavePublicStatsSettings(makerspaceId);
  const [draft, setDraft] = useState<PublicStatsSettings | null>(null);
  useEffect(() => { setDraft(null); }, [query.data]);
  if (!query.data) return query.error ? <p role="alert" className="py-4 text-sm text-danger">{query.error.message}</p>
    : <p className="py-4 text-sm text-muted">{t`Loading public stats settings…`}</p>;
  const { choices, can_edit: canEdit } = query.data;
  const value = draft ?? query.data.settings;
  const set = (patch: Partial<PublicStatsSettings>) => setDraft({ ...value, ...patch });
  const shownSections = new Set(value.sections);
  const toggleHeadline = (key: string, on: boolean) =>
    set({ headline: on ? [...value.headline, key] : value.headline.filter(item => item !== key) });
  const full = value.headline.length >= choices.max_headline;

  return <div className="grid">
    {!canEdit ? <div className="py-4"><Callout size="inline" tone="warn" lead="Only the Space Manager can change the public stats page." /></div> : null}
    <SettingsRow label={t`Public stats page`} helper={t`Event, community and headline counts below 3 show as “fewer than 3”. Borrower names follow the lending privacy setting.`}>
      <div className="grid gap-3">
        <StatusPill label={value.enabled ? t`On` : t`Off`} tone={value.enabled ? "success" : "neutral"} />
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={value.enabled}
          disabled={!canEdit} onChange={event => set({ enabled: event.target.checked })} />{t`Publish public stats`}</label>
        <ActionControl action={{ label: t`Preview the stats page`, href: `/m/${slug}/stats`, external: true }} />
      </div>
    </SettingsRow>
    <SettingsRow label={t`Sections and order`} helper={t`Tick the sections to show and move them into the order you want. A section whose module is off stays hidden.`}>
      <SectionOrderList choices={choices.sections} value={value.sections} disabled={!canEdit} onChange={sections => set({ sections })} />
    </SettingsRow>
    <SettingsRow label={t`Period`} helper={t`Every period count uses this one period. Visitors cannot change it.`}>
      <Field label={t`Stats period`}><select className="desk-input w-full" value={value.period} disabled={!canEdit}
        onChange={event => set({ period: event.target.value as PublicStatsSettings["period"] })}>
        {choices.periods.map(period => <option key={period.key} value={period.key}>{period.label}</option>)}
      </select></Field>
    </SettingsRow>
    <SettingsRow label={t`Headline numbers`} helper={t`Pick up to ${choices.max_headline}; they lead the page and the TV board in the order you tick them.`}>
      <fieldset className="grid gap-4"><legend className="sr-only">{t`Headline numbers`}</legend>
        {choices.sections.map(section => <div key={section.key} className="grid gap-1">
          <p className="text-sm font-semibold">{section.label}{shownSections.has(section.key) ? "" : t` (section hidden)`}</p>
          {choices.metrics.filter(metric => metric.section === section.key).map(metric => {
            const checked = value.headline.includes(metric.key);
            return <label key={metric.key} className="flex min-h-11 items-center gap-3 text-sm">
              <input type="checkbox" checked={checked} disabled={!canEdit || (!checked && full)}
                onChange={event => toggleHeadline(metric.key, event.target.checked)} />{metric.label}
              {checked ? <span className="text-xs text-muted">#{value.headline.indexOf(metric.key) + 1}</span> : null}</label>;
          })}
        </div>)}
      </fieldset>
    </SettingsRow>
    <SettingsRow label={t`TV mode`} helper={t`A full-screen board for a lobby screen. It refreshes itself and has no navigation.`}>
      <div className="grid gap-3">
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={value.tv_mode_enabled}
          disabled={!canEdit} onChange={event => set({ tv_mode_enabled: event.target.checked })} />{t`Turn on TV mode`}</label>
        <Field label={t`Refresh every (seconds, at least ${choices.tv_refresh_min})`}>
          <input type="number" className="desk-input max-w-40" min={choices.tv_refresh_min} max={choices.tv_refresh_max}
            value={value.tv_refresh_seconds} disabled={!canEdit}
            onChange={event => set({ tv_refresh_seconds: Number(event.target.value) })} /></Field>
        <ActionControl action={{ label: t`Preview TV mode`, href: `/m/${slug}/stats/tv`, external: true }} />
      </div>
    </SettingsRow>
    {canEdit ? <div className="flex flex-wrap gap-2 py-4">
      <button type="button" className="desk-button-primary" disabled={!draft || save.isPending}
        onClick={() => draft && save.mutate(draft)}>{save.isPending ? t`Saving…` : t`Save public stats`}</button>
      {draft ? <button type="button" className="desk-button" onClick={() => setDraft(null)}>{t`Discard`}</button> : null}
    </div> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
  </div>;
}
