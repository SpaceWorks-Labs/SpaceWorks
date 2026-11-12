import { t } from "@lingui/core/macro";
import { SettingsSection } from "../../../components/ui";
import { Field } from "../../members/memberProfile/Field";
import type { StatusPreset } from "../accountProfileTypes";
import { STATUS_PRESETS, statusLabel } from "../view/profileCopy";
import type { ProfileDraft } from "./profileDraft";
import { SectionToggle } from "./SectionToggle";

export const STATUS_NOTE_MAX = 120;

/** Status (preset plus a note up to 120 characters), then the about block: headline, institution and bio. */
export function StatusAboutFields({ draft, onChange }: { draft: ProfileDraft; onChange: (changes: Partial<ProfileDraft>) => void }) {
  return <>
    <SettingsSection title={t`Status`} description={t`A one-line signal of what you are up to.`}>
      <Field id="profile-status" label={t`Status`}>
        <select id="profile-status" className="desk-input w-full" value={draft.preset} onChange={event => onChange({ preset: event.target.value as StatusPreset })}>
          <option value="">{t`No status`}</option>
          {STATUS_PRESETS.map(preset => <option key={preset} value={preset}>{statusLabel(preset)}</option>)}
        </select>
      </Field>
      <Field id="profile-status-note" label={t`Note`} hint={t`${draft.note.length} of ${STATUS_NOTE_MAX} characters`}>
        <input id="profile-status-note" className="desk-input w-full" maxLength={STATUS_NOTE_MAX} value={draft.note} onChange={event => onChange({ note: event.target.value })} />
      </Field>
      <div className="py-3"><SectionToggle section="status" label={t`Show my status`} /></div>
    </SettingsSection>
    <SettingsSection title={t`About`}>
      <Field id="profile-headline" label={t`Headline`}>
        <input id="profile-headline" className="desk-input w-full" maxLength={200} value={draft.headline} onChange={event => onChange({ headline: event.target.value })} />
      </Field>
      <Field id="profile-institution" label={t`Institution`}>
        <input id="profile-institution" className="desk-input w-full" value={draft.institution} onChange={event => onChange({ institution: event.target.value })} />
      </Field>
      <Field id="profile-bio" label={t`Bio`}>
        <textarea id="profile-bio" className="desk-input w-full" rows={4} maxLength={2000} value={draft.bio} onChange={event => onChange({ bio: event.target.value })} />
      </Field>
      <div className="py-3"><SectionToggle section="about" label={t`Show my bio`} /></div>
    </SettingsSection>
  </>;
}
