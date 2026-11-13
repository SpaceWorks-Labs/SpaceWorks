import { t } from "@lingui/core/macro";
import { Field } from '../../../components/ui';

export type RoundSettings = { visibility: 'assigned' | 'all'; fresh_eyes: boolean; panel: string; share_feedback?: boolean; judge_reminders?: boolean };

/** L21b per-round settings: who may pull projects, a never-the-same-team rule and an optional panel. */
export function RoundSettingsFields({ value, onChange }: { value: RoundSettings; onChange: (next: RoundSettings) => void }) {
  return <fieldset className="grid gap-3 rounded-xl border border-line p-4"><legend className="px-1 font-semibold">{t`Round settings`}</legend>
    <Field label={t`What judges see`}><select className="desk-input min-h-11" value={value.visibility}
      onChange={e => onChange({ ...value, visibility: e.target.value as RoundSettings['visibility'] })}>
      <option value="assigned">{t`Only their assigned projects`}</option><option value="all">{t`Every project (“Score next” may pull any)`}</option></select></Field>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.fresh_eyes}
      onChange={e => onChange({ ...value, fresh_eyes: e.target.checked })} />{t`Fresh eyes: never give a judge a team they reviewed in an earlier round`}</label>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={Boolean(value.share_feedback)}
      onChange={e => onChange({ ...value, share_feedback: e.target.checked })} />{t`Share judges' team feedback with teams (no judge names) when this round's shortlist or results are published`}</label>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={Boolean(value.judge_reminders)}
      onChange={e => onChange({ ...value, judge_reminders: e.target.checked })} />{t`Remind judges with unfinished assignments (when the round opens, at its midpoint and a day before it closes)`}</label>
    <Field label={t`Judge panel (optional)`} hint={t`Judge role assignment IDs, separated by commas. Empty means every active judge.`}>
      <input className="desk-input min-h-11" value={value.panel} onChange={e => onChange({ ...value, panel: e.target.value })} /></Field>
  </fieldset>;
}

export function panelIds(text: string) {
  return text.split(',').map(part => Number(part.trim())).filter(id => Number.isSafeInteger(id) && id > 0);
}
